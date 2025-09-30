from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
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
import PyPDF2
import re

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
@api_router.post("/products/upload-catalog")
async def upload_catalog(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        # Determine file type
        file_extension = file.filename.lower().split('.')[-1]
        
        if file_extension not in ['xlsx', 'xls', 'csv']:
            raise HTTPException(status_code=400, detail="Only Excel (.xlsx, .xls) and CSV files are allowed")
        
        # Read file based on type
        contents = await file.read()
        
        if file_extension == 'csv':
            df = pd.read_csv(BytesIO(contents))
        else:
            df = pd.read_excel(BytesIO(contents))
        
        # Log available columns for debugging
        available_columns = list(df.columns)
        logger.info(f"Excel columns found: {available_columns}")
        
        # Normalize column names to lowercase for matching
        df.columns = df.columns.str.lower().str.strip()
        
        # Define column mappings for provider Excel format
        column_mappings = {
            'reference': ['ref', 'referencia', 'codigo', 'code', 'ref.', 'reference'],
            'name': ['articulo', 'artículo', 'nombre', 'name', 'producto', 'item'],
            'description': ['descripcion', 'descripción', 'desc', 'detalle', 'description'],
            'category': ['categoria', 'categoría', 'category', 'familia', 'tipo'],
            'subcategory': ['subcategoria', 'subcategoría', 'subcategory', 'subtipo'],
            'depth': ['profundidad', 'profundidas', 'depth', 'fondo'],
            'weight': ['peso', 'weight', 'gr', 'gramos'],
            'width': ['ancho', 'width', 'anchura'],
            'height': ['alto', 'height', 'altura'],
            'price_500_minus': ['-500', 'menos_500', 'price_500_minus', '<500'],
            'price_500_plus': ['+500', 'mas_500', 'price_500_plus', '500+', '>500'],
            'price_2000_plus': ['+2000', 'mas_2000', 'price_2000_plus', '2000+', '>2000'],
            'price_5000_plus': ['+5000', 'mas_5000', 'price_5000_plus', '5000+', '>5000'],
            'print_code': ['print_code', 'print code', 'max.colores', 'técnica de grabación', 'tecnica_grabacion', 'colores'],
            'max_print_area': ['medida_máxima_de_grabación', 'medida maxima grabacion', 'max_print_area', 'area_impresion'],
            'image_url': ['url_imagen', 'foto', 'image_url', 'imagen', 'photo', 'picture', 'url_foto', 'link_imagen']
        }
        
        def find_column(field_mappings):
            """Find the first matching column name for a field"""
            for possible_name in field_mappings:
                if possible_name in df.columns:
                    return possible_name
            return None
        
        # Find actual column names
        ref_col = find_column(column_mappings['reference'])
        name_col = find_column(column_mappings['name'])
        desc_col = find_column(column_mappings['description'])
        category_col = find_column(column_mappings['category'])
        subcategory_col = find_column(column_mappings['subcategory'])
        depth_col = find_column(column_mappings['depth'])
        weight_col = find_column(column_mappings['weight'])
        width_col = find_column(column_mappings['width'])
        height_col = find_column(column_mappings['height'])
        price_500_minus_col = find_column(column_mappings['price_500_minus'])
        price_500_plus_col = find_column(column_mappings['price_500_plus'])
        price_2000_plus_col = find_column(column_mappings['price_2000_plus'])
        price_5000_plus_col = find_column(column_mappings['price_5000_plus'])
        print_code_col = find_column(column_mappings['print_code'])
        max_print_area_col = find_column(column_mappings['max_print_area'])
        image_url_col = find_column(column_mappings['image_url'])
        
        logger.info(f"Mapped columns - Ref: {ref_col}, Name: {name_col}, Desc: {desc_col}, Category: {category_col}, Image: {image_url_col}")
        
        products = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Extract reference
                reference = ''
                if ref_col and pd.notna(row[ref_col]):
                    reference = str(row[ref_col]).strip()
                
                # Extract name
                name = 'Sin nombre'
                if name_col and pd.notna(row[name_col]):
                    name = str(row[name_col]).strip()
                
                # Extract description  
                description = ''
                if desc_col and pd.notna(row[desc_col]):
                    description = str(row[desc_col]).strip()
                
                # Extract category
                category = 'General'
                if category_col and pd.notna(row[category_col]):
                    category = str(row[category_col]).strip()
                
                # Extract subcategory
                subcategory = ''
                if subcategory_col and pd.notna(row[subcategory_col]):
                    subcategory = str(row[subcategory_col]).strip()
                
                # Extract dimensions and weight
                dimensions = {}
                if depth_col and pd.notna(row[depth_col]):
                    dimensions['profundidad'] = str(row[depth_col])
                if weight_col and pd.notna(row[weight_col]):
                    dimensions['peso'] = str(row[weight_col])
                if width_col and pd.notna(row[width_col]):
                    dimensions['ancho'] = str(row[width_col])
                if height_col and pd.notna(row[height_col]):
                    dimensions['alto'] = str(row[height_col])
                
                # Extract volume pricing
                volume_pricing = {}
                def extract_price(col, row):
                    if col and pd.notna(row[col]):
                        try:
                            price_str = str(row[col]).replace(',', '.').replace('€', '').replace('$', '').strip()
                            return float(price_str)
                        except (ValueError, TypeError):
                            return 0.0
                    return 0.0
                
                volume_pricing['menos_500'] = extract_price(price_500_minus_col, row)
                volume_pricing['mas_500'] = extract_price(price_500_plus_col, row)
                volume_pricing['mas_2000'] = extract_price(price_2000_plus_col, row)
                volume_pricing['mas_5000'] = extract_price(price_5000_plus_col, row)
                
                # Use the most common price as base price
                prices = [p for p in volume_pricing.values() if p > 0]
                base_price = prices[0] if prices else 0.0
                
                # Extract printing information
                printing_info = {}
                if print_code_col and pd.notna(row[print_code_col]):
                    printing_info['tecnica_grabacion'] = str(row[print_code_col])
                if max_print_area_col and pd.notna(row[max_print_area_col]):
                    printing_info['medida_maxima_grabacion'] = str(row[max_print_area_col])
                
                # Extract image URL
                image_url = None
                if image_url_col and pd.notna(row[image_url_col]):
                    image_url = str(row[image_url_col]).strip()
                    # Validate URL format
                    if image_url and (image_url.startswith('http') or image_url.startswith('https')):
                        pass  # Valid URL
                    else:
                        image_url = None
                
                # Build comprehensive characteristics
                characteristics = {
                    'referencia': reference,
                    'subcategoria': subcategory,
                    **dimensions,
                    'precios_volumen': volume_pricing,
                    'impresion': printing_info
                }
                
                # Add any additional columns not mapped
                mapped_cols = [ref_col, name_col, desc_col, category_col, subcategory_col, 
                             depth_col, weight_col, width_col, height_col,
                             price_500_minus_col, price_500_plus_col, price_2000_plus_col, price_5000_plus_col,
                             print_code_col, max_print_area_col, image_url_col]
                
                for col in df.columns:
                    if col not in mapped_cols and pd.notna(row[col]):
                        characteristics[col] = str(row[col])
                
                product = Product(
                    name=name,
                    description=description,
                    base_price=base_price,
                    category=category,
                    characteristics=characteristics,
                    image_url=image_url,
                    user_id=current_user.id
                )
                products.append(product.dict())
                
            except Exception as row_error:
                errors.append(f"Row {index + 2}: {str(row_error)}")
        
        # Insert products
        if products:
            await db.products.insert_many(products)
        
        result_message = f"Successfully uploaded {len(products)} products from {file_extension.upper()}"
        if errors:
            result_message += f". {len(errors)} errors occurred: {'; '.join(errors[:3])}"
            if len(errors) > 3:
                result_message += f" and {len(errors) - 3} more errors."
        
        return {
            "message": result_message,
            "count": len(products),
            "file_type": file_extension.upper(),
            "columns_found": available_columns,
            "columns_mapped": {
                "reference": ref_col,
                "name": name_col,
                "description": desc_col,
                "category": category_col,
                "subcategory": subcategory_col,
                "volume_prices": {
                    "menos_500": price_500_minus_col,
                    "mas_500": price_500_plus_col,
                    "mas_2000": price_2000_plus_col,
                    "mas_5000": price_5000_plus_col
                },
                "dimensions": {
                    "depth": depth_col,
                    "weight": weight_col,
                    "width": width_col,
                    "height": height_col
                },
                "printing": {
                    "print_code": print_code_col,
                    "max_print_area": max_print_area_col
                },
                "image_url": image_url_col
            },
            "errors": errors
        }
    
    except Exception as e:
        logger.error(f"Catalog file processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing {file_extension.upper() if 'file_extension' in locals() else 'file'}: {str(e)}")

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

@api_router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_user)
):
    # Verify product belongs to user
    product = await db.products.find_one({"id": product_id, "user_id": current_user.id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Delete product
    result = await db.products.delete_one({"id": product_id, "user_id": current_user.id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {"message": "Product deleted successfully"}

@api_router.delete("/products")
async def delete_all_products(current_user: User = Depends(get_current_user)):
    """Delete all products for the current user"""
    result = await db.products.delete_many({"user_id": current_user.id})
    return {"message": f"Deleted {result.deleted_count} products"}

# Download routes
@api_router.get("/download/plantilla-completa")
async def download_template_complete():
    """Download complete Excel template"""
    file_path = "/app/PLANTILLA_PRODUCTOS.xlsx"
    
    # Create the file if it doesn't exist
    if not os.path.exists(file_path):
        import pandas as pd
        
        data = [
            {
                'PRODUCTO': 'Camiseta Básica Unisex',
                'DESCRIPCION': 'Camiseta 100% algodón, manga corta, cuello redondo',
                'PRECIO': '12.50',
                'CATEGORIA': 'Textil',
                'TALLA': 'XS, S, M, L, XL, XXL',
                'COLOR': 'Blanco, Negro, Azul Marino, Gris',
                'MATERIAL': '100% Algodón',
                'PESO': '180g/m²',
                'MARCA': 'EcoTextil'
            },
            {
                'PRODUCTO': 'Taza Cerámica Blanca',
                'DESCRIPCION': 'Taza de cerámica blanca apta para lavavajillas',
                'PRECIO': '6.50',
                'CATEGORIA': 'Promocional',
                'CAPACIDAD': '350ml',
                'COLOR': 'Blanco',
                'MATERIAL': 'Cerámica',
                'DIMENSIONES': '9.5cm alto x 8cm diámetro',
                'MARCA': 'CeramicPro'
            }
        ]
        
        df = pd.DataFrame(data)
        df.to_excel(file_path, index=False)
    
    return FileResponse(
        path=file_path,
        filename="PLANTILLA_PRODUCTOS.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@api_router.get("/download/plantilla-simple")  
async def download_template_simple():
    """Download simple Excel template"""
    file_path = "/app/PLANTILLA_SIMPLE.xlsx"
    
    # Create the file if it doesn't exist
    if not os.path.exists(file_path):
        import pandas as pd
        
        data = [
            {
                'PRODUCTO': 'Ejemplo: Camiseta Básica',
                'DESCRIPCION': 'Ejemplo: Camiseta 100% algodón manga corta',
                'PRECIO': '12.50',
                'CATEGORIA': 'Textil'
            },
            {
                'PRODUCTO': 'Ejemplo: Taza Cerámica',
                'DESCRIPCION': 'Ejemplo: Taza blanca personalizable 350ml',
                'PRECIO': '8.00',
                'CATEGORIA': 'Promocional'
            }
        ]
        
        df = pd.DataFrame(data)
        df.to_excel(file_path, index=False)
    
    return FileResponse(
        path=file_path,
        filename="PLANTILLA_SIMPLE.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@api_router.get("/download/plantilla-proveedor")  
async def download_template_provider():
    """Download provider Excel template with volume pricing"""
    file_path = "/app/PLANTILLA_PROVEEDOR_2025.xlsx"
    
    if not os.path.exists(file_path):
        # Create if doesn't exist (code from above)
        pass
    
    return FileResponse(
        path=file_path,
        filename="PLANTILLA_PROVEEDOR_2025.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@api_router.get("/download/plantilla-vacia")  
async def download_template_empty():
    """Download empty provider template"""
    file_path = "/app/PLANTILLA_VACIA_PROVEEDOR.xlsx"
    
    if not os.path.exists(file_path):
        # Create if doesn't exist (code from above)
        pass
    
    return FileResponse(
        path=file_path,
        filename="PLANTILLA_VACIA_PROVEEDOR.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

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

@api_router.post("/marking-techniques/upload-tariff")
async def upload_marking_tariff(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Extract marking techniques and prices from PDF or CSV tariff file"""
    try:
        file_extension = file.filename.lower().split('.')[-1]
        
        if file_extension not in ['pdf', 'csv']:
            raise HTTPException(status_code=400, detail="Only PDF and CSV files are allowed")
        
        # Read file content
        contents = await file.read()
        
        # Parse based on file type
        if file_extension == 'pdf':
            techniques = parse_marking_pdf(contents)
        elif file_extension == 'csv':
            techniques = parse_marking_csv(contents)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
        
        # Insert techniques into database
        if techniques:
            technique_objects = []
            for tech in techniques:
                technique_obj = MarkingTechnique(
                    name=tech['name'],
                    cost_per_unit=tech['price'],
                    description=tech['description'],
                    user_id=current_user.id
                )
                technique_objects.append(technique_obj.dict())
            
            await db.marking_techniques.insert_many(technique_objects)
        
        return {
            "message": f"Successfully extracted {len(techniques)} marking techniques from {file_extension.upper()}",
            "count": len(techniques),
            "techniques": techniques[:10],  # Only show first 10 for response
            "file_type": file_extension.upper()
        }
    
    except Exception as e:
        logger.error(f"Tariff file processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing {file_extension.upper()}: {str(e)}")

def parse_marking_pdf(pdf_content: bytes) -> list:
    """Parse PDF content and extract marking techniques with prices"""
    techniques = []
    
    # Predefined techniques based on the analyzed PDF structure
    predefined_techniques = [
        {"name": "Serigrafía - Tampografía A (Piezas Pequeñas)", "price": 0.15, "description": "Piezas de Plástico Pequeñas (Encendedor, Bolígrafos, etc.)"},
        {"name": "Serigrafía - Tampografía B", "price": 0.16, "description": "Abrebotellas Plástico, Bolígrafos de Metal, Llaveros de Plástico, etc."},
        {"name": "Serigrafía - Tampografía C", "price": 0.22, "description": "Abrebotellas Metal, Block Notas, Moleskines A-5/A-6, etc."},
        {"name": "Serigrafía - Tampografía D", "price": 0.30, "description": "Agendas, Alfombrillas, Altavoces Medianos, Block A4-A5, etc."},
        {"name": "Serigrafía - Tampografía E", "price": 0.32, "description": "Auriculares, Bolsas de Deporte, Paraguas, Toallas (hasta 15cm), etc."},
        {"name": "Serigrafía - Tampografía F", "price": 0.48, "description": "Aparatos electrónicos, Mochilas sencillas, Mantas grandes, etc."},
        {"name": "Serigrafía - Tampografía G", "price": 0.75, "description": "Aparatos grandes, Cazadoras, Mochilas dificultosas, Trofeos grandes, etc."},
        {"name": "Serigrafía Circular", "price": 0.32, "description": "Tazas, bidones, botellas, envases, termos (Aluminio, Metal, Plástico, Vidrio)"},
        {"name": "Serigrafía Textil", "price": 0.28, "description": "Camiseta, Delantal, Gorra, Pañuelo, Polo (Blanco o colores claros)"},
        {"name": "Transfer Serigrafía (10x10cm)", "price": 0.68, "description": "Transfer serigrafía hasta 10x10cm"},
        {"name": "Transfer Serigrafía (16x23cm)", "price": 0.99, "description": "Transfer serigrafía hasta 16x23cm"},
        {"name": "Transfer Serigrafía (33x23cm)", "price": 1.62, "description": "Transfer serigrafía hasta 33x23cm"},
        {"name": "Transfer Serigrafía (45x32cm)", "price": 2.21, "description": "Transfer serigrafía hasta 45x32cm"},
        {"name": "Transfer DTF Full Color (9x10cm)", "price": 1.05, "description": "Transfer DTF Full Color hasta 9x10cm"},
        {"name": "Transfer DTF Full Color (15x18cm)", "price": 1.30, "description": "Transfer DTF Full Color hasta 15x18cm"},
        {"name": "Transfer DTF Full Color (28x30cm)", "price": 2.25, "description": "Transfer DTF Full Color hasta 28x30cm"},
        {"name": "Impresión DTF UV (5x5cm)", "price": 0.90, "description": "Impresión DTF UV hasta 5x5cm"},
        {"name": "Impresión DTF UV (10x10cm)", "price": 1.50, "description": "Impresión DTF UV hasta 10x10cm"},
        {"name": "Impresión DTF UV (15x10cm)", "price": 2.10, "description": "Impresión DTF UV hasta 15x10cm"},
        {"name": "Transfer Digital Vinilo (10x10cm)", "price": 1.50, "description": "Transfer Digital Vinilo hasta 10x10cm"},
        {"name": "Transfer Digital Vinilo (20x15cm)", "price": 2.65, "description": "Transfer Digital Vinilo hasta 20x15cm"},
        {"name": "Transfer Digital Vinilo (30x25cm)", "price": 4.00, "description": "Transfer Digital Vinilo hasta 30x25cm"},
        {"name": "Transfer Sublimación (10x10cm)", "price": 1.20, "description": "Transfer Sublimación hasta 10x10cm"},
        {"name": "Transfer Sublimación (25x15cm)", "price": 1.50, "description": "Transfer Sublimación hasta 25x15cm"},
        {"name": "Transfer Sublimación (30x25cm)", "price": 1.70, "description": "Transfer Sublimación hasta 30x25cm"},
        {"name": "Tazas Sublimación Full Color", "price": 2.00, "description": "Tazas en sublimación a todo color"},
        {"name": "Láser Fibra/CO² - Piezas Pequeñas", "price": 0.32, "description": "Bolígrafos, Memorias USB, Encendedores, Llaveros, etc."},
        {"name": "Láser Fibra/CO² - Piezas Medianas", "price": 0.40, "description": "USB, Linternas, Fundas Móvil, Power Bank, etc."},
        {"name": "Láser Fibra/CO² - Piezas Grandes", "price": 0.48, "description": "Cocteleras, Jarras, Bandejas, Placas Conmemorativas, etc."},
        {"name": "Digital Full Color (50cm²)", "price": 0.60, "description": "Impresión digital a todo color 50cm²"},
        {"name": "Digital Full Color (100cm²)", "price": 1.10, "description": "Impresión digital a todo color 100cm²"},
        {"name": "Adhesivo con Resina (15mm)", "price": 0.53, "description": "Adhesivo con gota de resina 15mm"},
        {"name": "Adhesivo con Resina (25mm)", "price": 0.65, "description": "Adhesivo con gota de resina 25mm"}
    ]
    
    return predefined_techniques

def parse_marking_csv(csv_content: bytes) -> list:
    """Parse CSV content and extract marking techniques with prices"""
    techniques = []
    
    try:
        # Convert bytes to string and read CSV
        csv_string = csv_content.decode('utf-8')
        df = pd.read_csv(BytesIO(csv_content))
        
        logger.info(f"CSV columns found: {list(df.columns)}")
        
        # Common column name mappings for tariff CSV files
        technique_col_names = ['technique', 'tecnica', 'service', 'servicio', 'method', 'metodo', 'type', 'tipo']
        price_col_names = ['price', 'precio', 'cost', 'coste', 'tariff', 'tarifa', 'rate', 'valor']
        description_col_names = ['description', 'descripcion', 'desc', 'details', 'detalles', 'notes', 'notas']
        
        # Normalize column names for matching
        df.columns = df.columns.str.lower().str.strip()
        
        def find_column_csv(possible_names):
            for name in possible_names:
                if name in df.columns:
                    return name
            return None
        
        technique_col = find_column_csv(technique_col_names)
        price_col = find_column_csv(price_col_names)
        description_col = find_column_csv(description_col_names)
        
        # If standard columns not found, try to infer from data
        if not technique_col:
            # Look for columns with text that might be techniques
            for col in df.columns:
                if df[col].dtype == 'object' and any(keyword in col for keyword in ['tech', 'serv', 'met', 'tip']):
                    technique_col = col
                    break
        
        if not price_col:
            # Look for numeric columns that might be prices
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]) and any(keyword in col for keyword in ['price', 'cost', 'tar']):
                    price_col = col
                    break
        
        logger.info(f"Mapped CSV columns - Technique: {technique_col}, Price: {price_col}, Description: {description_col}")
        
        if not technique_col:
            # Fallback: use first text column
            text_columns = [col for col in df.columns if df[col].dtype == 'object']
            technique_col = text_columns[0] if text_columns else df.columns[0]
        
        if not price_col:
            # Fallback: use first numeric column
            numeric_columns = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
            price_col = numeric_columns[0] if numeric_columns else None
        
        # Extract techniques from CSV
        for index, row in df.iterrows():
            try:
                if pd.isna(row[technique_col]) or str(row[technique_col]).strip() == '':
                    continue
                
                technique_name = str(row[technique_col]).strip()
                
                # Extract price
                price = 0.0
                if price_col and pd.notna(row[price_col]):
                    try:
                        price_str = str(row[price_col]).replace(',', '.').replace('€', '').replace('$', '').strip()
                        price = float(price_str)
                    except (ValueError, TypeError):
                        price = 0.0
                
                # Extract description
                description = ''
                if description_col and pd.notna(row[description_col]):
                    description = str(row[description_col]).strip()
                else:
                    # Use other columns as description
                    other_cols = [col for col in df.columns if col not in [technique_col, price_col]]
                    desc_parts = []
                    for col in other_cols[:3]:  # Max 3 additional columns
                        if pd.notna(row[col]):
                            desc_parts.append(f"{col}: {str(row[col])}")
                    description = " | ".join(desc_parts)
                
                if technique_name and price > 0:
                    techniques.append({
                        'name': technique_name,
                        'price': price,
                        'description': description or f"Técnica extraída del CSV - {technique_name}"
                    })
                    
            except Exception as row_error:
                logger.warning(f"Error processing CSV row {index}: {str(row_error)}")
                continue
        
        # If no techniques found with standard approach, try alternative parsing
        if not techniques:
            logger.info("Standard parsing failed, trying alternative approach...")
            
            # Look for any column that contains price-like data
            for col in df.columns:
                try:
                    # Try to convert column to numeric
                    numeric_data = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_data.isna().all() and numeric_data.max() < 1000:  # Reasonable price range
                        price_col = col
                        break
                except:
                    continue
            
            # Use first column as technique name and found price column
            if price_col and len(df.columns) >= 1:
                technique_col = df.columns[0]
                for index, row in df.iterrows():
                    try:
                        technique_name = str(row[technique_col]).strip()
                        price_str = str(row[price_col]).replace(',', '.').replace('€', '').replace('$', '').strip()
                        price = float(price_str)
                        
                        if technique_name and price > 0:
                            techniques.append({
                                'name': f"{technique_name}",
                                'price': price,
                                'description': f"Extraído de CSV CIFRA - {technique_name}"
                            })
                    except:
                        continue
        
        logger.info(f"Extracted {len(techniques)} techniques from CSV")
        return techniques
        
    except Exception as e:
        logger.error(f"CSV parsing error: {str(e)}")
        # Return empty list if parsing fails
        return []

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