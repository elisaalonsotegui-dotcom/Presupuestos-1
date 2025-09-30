from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from passlib.context import CryptContext
import pandas as pd
from io import BytesIO
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Security
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_TIME_MINUTES = 60 * 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI(title="Presupuestos App")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    username: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_active: bool

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    base_price: float
    category: str
    characteristics: Dict[str, Any]
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str

class ProductCreate(BaseModel):
    name: str
    description: str
    base_price: float
    category: str
    characteristics: Dict[str, Any]

class MarkingTechnique(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    cost_per_unit: float
    description: str
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MarkingTechniqueCreate(BaseModel):
    name: str
    cost_per_unit: float
    description: str

class Quote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    products: List[Dict[str, Any]]
    total_basic: float
    total_medium: float
    total_premium: float
    marking_techniques: List[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str

class QuoteCreate(BaseModel):
    client_name: str
    search_criteria: Dict[str, Any]
    marking_techniques: List[str]

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    # Truncate password to 72 bytes for bcrypt compatibility
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRATION_TIME_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user)

# Auth routes
@api_router.post("/auth/register", response_model=Token)
async def register(user_create: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_create.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user_create.password)
    user = User(
        email=user_create.email,
        username=user_create.username
    )
    
    user_dict = user.dict()
    user_dict["hashed_password"] = hashed_password
    
    await db.users.insert_one(user_dict)
    
    # Create token
    access_token_expires = timedelta(minutes=JWT_EXPIRATION_TIME_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(**user.dict())
    )

@api_router.post("/auth/login", response_model=Token)
async def login(user_login: UserLogin):
    user = await db.users.find_one({"email": user_login.email})
    if not user or not verify_password(user_login.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token_expires = timedelta(minutes=JWT_EXPIRATION_TIME_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]}, expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(**user)
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(**current_user.dict())

# Product routes
@api_router.post("/products/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        # Read Excel file
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        
        # Log available columns for debugging
        available_columns = list(df.columns)
        logger.info(f"Excel columns found: {available_columns}")
        
        # Normalize column names to lowercase for matching
        df.columns = df.columns.str.lower().str.strip()
        
        # Define column mappings (multiple possible names for each field)
        column_mappings = {
            'name': ['nombre', 'name', 'producto', 'articulo', 'item', 'descripción_corta', 'title'],
            'description': ['descripcion', 'description', 'descripción', 'desc', 'detalle', 'detalles'],
            'price': ['precio', 'price', 'coste', 'cost', 'valor', 'importe', 'pvp', 'tarifa'],
            'category': ['categoria', 'category', 'categoría', 'tipo', 'clase', 'familia', 'grupo'],
            'characteristics': ['caracteristicas', 'características', 'specs', 'specifications', 'propiedades', 'atributos']
        }
        
        def find_column(field_mappings):
            """Find the first matching column name for a field"""
            for possible_name in field_mappings:
                if possible_name in df.columns:
                    return possible_name
            return None
        
        # Find actual column names
        name_col = find_column(column_mappings['name'])
        desc_col = find_column(column_mappings['description'])
        price_col = find_column(column_mappings['price'])
        category_col = find_column(column_mappings['category'])
        char_col = find_column(column_mappings['characteristics'])
        
        logger.info(f"Mapped columns - Name: {name_col}, Desc: {desc_col}, Price: {price_col}, Category: {category_col}, Chars: {char_col}")
        
        products = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Extract name
                name = 'Sin nombre'
                if name_col and pd.notna(row[name_col]):
                    name = str(row[name_col]).strip()
                
                # Extract description  
                description = ''
                if desc_col and pd.notna(row[desc_col]):
                    description = str(row[desc_col]).strip()
                
                # Extract price
                price = 0.0
                if price_col and pd.notna(row[price_col]):
                    try:
                        # Handle different price formats
                        price_str = str(row[price_col]).replace(',', '.').replace('€', '').replace('$', '').strip()
                        price = float(price_str)
                    except (ValueError, TypeError):
                        price = 0.0
                
                # Extract category
                category = 'General'
                if category_col and pd.notna(row[category_col]):
                    category = str(row[category_col]).strip()
                
                # Extract characteristics
                characteristics = {}
                if char_col and pd.notna(row[char_col]):
                    try:
                        char_value = row[char_col]
                        if isinstance(char_value, str):
                            # Try to parse as JSON first
                            try:
                                characteristics = json.loads(char_value)
                            except json.JSONDecodeError:
                                # If not JSON, store as raw text
                                characteristics = {"descripcion": char_value}
                        else:
                            characteristics = {"valor": str(char_value)}
                    except:
                        characteristics = {}
                
                # Create additional characteristics from other columns
                for col in df.columns:
                    if col not in [name_col, desc_col, price_col, category_col, char_col] and pd.notna(row[col]):
                        characteristics[col] = str(row[col])
                
                product = Product(
                    name=name,
                    description=description,
                    base_price=price,
                    category=category,
                    characteristics=characteristics,
                    user_id=current_user.id
                )
                products.append(product.dict())
                
            except Exception as row_error:
                errors.append(f"Row {index + 2}: {str(row_error)}")
        
        # Insert products
        if products:
            await db.products.insert_many(products)
        
        result_message = f"Successfully uploaded {len(products)} products"
        if errors:
            result_message += f". {len(errors)} errors occurred: {'; '.join(errors[:3])}"
            if len(errors) > 3:
                result_message += f" and {len(errors) - 3} more errors."
        
        return {
            "message": result_message,
            "count": len(products),
            "columns_found": available_columns,
            "columns_mapped": {
                "name": name_col,
                "description": desc_col, 
                "price": price_col,
                "category": category_col,
                "characteristics": char_col
            },
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Excel processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing Excel file: {str(e)}")

@api_router.get("/products", response_model=List[Product])
async def get_products(current_user: User = Depends(get_current_user)):
    products = await db.products.find({"user_id": current_user.id}).to_list(length=None)
    return [Product(**product) for product in products]

@api_router.post("/products", response_model=Product)
async def create_product(
    product_create: ProductCreate,
    current_user: User = Depends(get_current_user)
):
    product = Product(**product_create.dict(), user_id=current_user.id)
    await db.products.insert_one(product.dict())
    return product

# Marking techniques routes
@api_router.post("/marking-techniques", response_model=MarkingTechnique)
async def create_marking_technique(
    technique_create: MarkingTechniqueCreate,
    current_user: User = Depends(get_current_user)
):
    technique = MarkingTechnique(**technique_create.dict(), user_id=current_user.id)
    await db.marking_techniques.insert_one(technique.dict())
    return technique

@api_router.get("/marking-techniques", response_model=List[MarkingTechnique])
async def get_marking_techniques(current_user: User = Depends(get_current_user)):
    techniques = await db.marking_techniques.find({"user_id": current_user.id}).to_list(length=None)
    return [MarkingTechnique(**technique) for technique in techniques]

# Quote routes
@api_router.post("/quotes/generate", response_model=Quote)
async def generate_quote(
    quote_create: QuoteCreate,
    current_user: User = Depends(get_current_user)
):
    # Search products based on criteria
    search_filter = {"user_id": current_user.id}
    
    # Add search criteria filters
    if "category" in quote_create.search_criteria:
        search_filter["category"] = {"$regex": quote_create.search_criteria["category"], "$options": "i"}
    
    products = await db.products.find(search_filter).to_list(length=None)
    
    if not products:
        raise HTTPException(status_code=404, detail="No products found matching criteria")
    
    # Sort products by price for tiered quotes
    products.sort(key=lambda x: x["base_price"])
    
    # Get marking costs
    marking_costs = 0
    if quote_create.marking_techniques:
        techniques = await db.marking_techniques.find({
            "user_id": current_user.id,
            "name": {"$in": quote_create.marking_techniques}
        }).to_list(length=None)
        marking_costs = sum(t["cost_per_unit"] for t in techniques)
    
    # Generate three tiers
    total_products = len(products)
    
    # Clean products data to remove MongoDB ObjectIds
    def clean_product(product):
        cleaned = {k: v for k, v in product.items() if k != '_id'}
        return cleaned
    
    # Basic: cheapest 1/3
    basic_products = [clean_product(p) for p in products[:max(1, total_products // 3)]]
    basic_total = sum(p["base_price"] for p in basic_products) + marking_costs
    
    # Medium: middle 1/3
    medium_start = max(1, total_products // 3)
    medium_end = max(2, (2 * total_products) // 3)
    medium_products_raw = products[medium_start:medium_end] if medium_end > medium_start else products[:2]
    medium_products = [clean_product(p) for p in medium_products_raw]
    medium_total = sum(p["base_price"] for p in medium_products) + marking_costs * 1.5
    
    # Premium: most expensive 1/3
    premium_start = max(2, (2 * total_products) // 3)
    premium_products_raw = products[premium_start:]
    if not premium_products_raw:
        premium_products_raw = products[-2:]
    premium_products = [clean_product(p) for p in premium_products_raw]
    premium_total = sum(p["base_price"] for p in premium_products) + marking_costs * 2
    
    quote = Quote(
        client_name=quote_create.client_name,
        products=[
            {"basic": basic_products, "medium": medium_products, "premium": premium_products}
        ],
        total_basic=basic_total,
        total_medium=medium_total,
        total_premium=premium_total,
        marking_techniques=quote_create.marking_techniques,
        user_id=current_user.id
    )
    
    await db.quotes.insert_one(quote.dict())
    return quote

@api_router.get("/quotes", response_model=List[Quote])
async def get_quotes(current_user: User = Depends(get_current_user)):
    quotes = await db.quotes.find({"user_id": current_user.id}).sort("created_at", -1).to_list(length=None)
    return [Quote(**quote) for quote in quotes]

@api_router.get("/quotes/{quote_id}", response_model=Quote)
async def get_quote(quote_id: str, current_user: User = Depends(get_current_user)):
    quote = await db.quotes.find_one({"id": quote_id, "user_id": current_user.id})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return Quote(**quote)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()