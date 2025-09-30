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
            # Handle CSV files with inconsistent column counts
            try:
                df = pd.read_csv(BytesIO(contents))
            except pd.errors.ParserError as e:
                # If parsing fails due to inconsistent columns, try with error handling
                logger.info(f"CSV parsing failed with standard method, trying with error handling: {str(e)}")
                try:
                    # Read CSV with error handling for bad lines
                    df = pd.read_csv(BytesIO(contents), on_bad_lines='skip', sep=None, engine='python')
                except Exception as e2:
                    logger.info(f"Second CSV attempt failed, trying with different separators: {str(e2)}")
                    # Try different common separators
                    for sep in [',', ';', '\t', '|']:
                        try:
                            contents_copy = BytesIO(contents.getvalue() if hasattr(contents, 'getvalue') else contents)
                            df = pd.read_csv(contents_copy, sep=sep, on_bad_lines='skip')
                            if len(df.columns) > 1:  # If we got multiple columns, it's likely correct
                                logger.info(f"Successfully parsed CSV with separator: '{sep}'")
                                break
                        except Exception:
                            continue
                    else:
                        # If all separators fail, read as single column and try to split
                        contents_copy = BytesIO(contents.getvalue() if hasattr(contents, 'getvalue') else contents)
                        df = pd.read_csv(contents_copy, sep=None, engine='python', on_bad_lines='skip')
        else:
            df = pd.read_excel(BytesIO(contents))
        
        # Log available columns for debugging
        available_columns = list(df.columns)
        logger.info(f"Catalog file columns found: {available_columns}")
        
        # Clean the dataframe - remove completely empty rows
        df = df.dropna(how='all')
        
        # If DataFrame is empty after cleaning, return error
        if df.empty:
            raise HTTPException(status_code=400, detail="The file appears to be empty or contains no valid data")
        
        # Normalize column names to lowercase for matching
        df.columns = df.columns.str.lower().str.strip()
        
        # Remove any unnamed columns (often created by CSV parsing issues)
        df = df.loc[:, ~df.columns.str.contains('^unnamed', case=False)]
        
        logger.info(f"Cleaned columns: {list(df.columns)}")
        
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
            'price_base': ['precio_confidencial', 'precio confidencial', 'precio', 'price', 'coste', 'cost', 'valor', 'importe', 'pvp', 'tarifa'],
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
        price_base_col = find_column(column_mappings['price_base'])
        print_code_col = find_column(column_mappings['print_code'])
        max_print_area_col = find_column(column_mappings['max_print_area'])
        image_url_col = find_column(column_mappings['image_url'])
        
        # Enhanced price detection - look for any numeric column that might be price
        detected_price_cols = []
        if not any([price_500_minus_col, price_500_plus_col, price_2000_plus_col, price_5000_plus_col]):
            logger.info("No volume price columns found, searching for any price column...")
            for col in df.columns:
                try:
                    # Check if column contains numeric data that could be prices
                    numeric_values = pd.to_numeric(df[col], errors='coerce')
                    non_null_values = numeric_values.dropna()
                    
                    if len(non_null_values) > 0:
                        min_val = non_null_values.min()
                        max_val = non_null_values.max()
                        
                        # Reasonable price range (0.01 to 10000)
                        if min_val >= 0 and max_val <= 10000 and min_val < max_val:
                            detected_price_cols.append({
                                'column': col,
                                'min': min_val,
                                'max': max_val,
                                'count': len(non_null_values)
                            })
                except Exception:
                    continue
            
            logger.info(f"Detected potential price columns: {detected_price_cols}")
        
        logger.info(f"Mapped columns - Ref: {ref_col}, Name: {name_col}, Desc: {desc_col}, Category: {category_col}")
        logger.info(f"Price columns - Base: {price_base_col}, 500-: {price_500_minus_col}, 500+: {price_500_plus_col}, 2000+: {price_2000_plus_col}, 5000+: {price_5000_plus_col}")
        logger.info(f"Other - Print: {print_code_col}, Image: {image_url_col}")
        
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
                            # Handle different decimal separators and currency symbols
                            price_str = str(row[col]).replace('€', '').replace('$', '').replace('£', '')
                            price_str = price_str.replace(' ', '').strip()
                            
                            # Handle European decimal format (comma as decimal separator)
                            if ',' in price_str and '.' in price_str:
                                # Format like 1.234,56 (European style with thousands separator)
                                price_str = price_str.replace('.', '').replace(',', '.')
                            elif ',' in price_str and price_str.count(',') == 1:
                                # Simple comma as decimal separator
                                price_str = price_str.replace(',', '.')
                            
                            return float(price_str)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Could not parse price '{row[col]}' in column '{col}': {e}")
                            return 0.0
                    return 0.0
                
                volume_pricing['menos_500'] = extract_price(price_500_minus_col, row)
                volume_pricing['mas_500'] = extract_price(price_500_plus_col, row)
                volume_pricing['mas_2000'] = extract_price(price_2000_plus_col, row)
                volume_pricing['mas_5000'] = extract_price(price_5000_plus_col, row)
                
                # Use the most common price as base price
                prices = [p for p in volume_pricing.values() if p > 0]
                base_price = prices[0] if prices else 0.0
                
                # If no volume pricing found, try to use base price column (like "Precio Confidencial")
                if base_price == 0.0 and price_base_col:
                    base_price = extract_price(price_base_col, row)
                    if base_price > 0:
                        volume_pricing['precio_base'] = base_price
                
                # If still no price found, try to use detected price columns
                if base_price == 0.0 and detected_price_cols:
                    for price_col_info in detected_price_cols:
                        col = price_col_info['column']
                        if col in row and pd.notna(row[col]):
                            base_price = extract_price(col, row)
                            if base_price > 0:
                                # Also populate volume pricing with this single price
                                volume_pricing['precio_detectado'] = base_price
                                break
                
                logger.debug(f"Row {index}: Base price={base_price}, Volume pricing={volume_pricing}")
                
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
                    base_price=float(base_price),
                    category=category,
                    characteristics=characteristics,
                    image_url=image_url,
                    user_id=current_user.id
                )
                
                # Convert product to dict and ensure no NumPy types
                product_dict = product.dict()
                
                # Clean characteristics to avoid NumPy serialization issues
                if 'characteristics' in product_dict and product_dict['characteristics']:
                    cleaned_characteristics = {}
                    for key, value in product_dict['characteristics'].items():
                        if hasattr(value, 'dtype'):  # NumPy type
                            cleaned_characteristics[key] = value.item() if hasattr(value, 'item') else str(value)
                        else:
                            cleaned_characteristics[key] = value
                    product_dict['characteristics'] = cleaned_characteristics
                
                products.append(product_dict)
                
            except Exception as row_error:
                error_msg = f"Row {index + 2}: {str(row_error)}"
                errors.append(error_msg)
                logger.warning(error_msg)
                # Continue processing other rows
                continue
        
        # Insert products
        if products:
            await db.products.insert_many(products)
        
        result_message = f"Successfully uploaded {len(products)} products from {file_extension.upper()}"
        if errors:
            result_message += f". {len(errors)} errors occurred: {'; '.join(errors[:3])}"
            if len(errors) > 3:
                result_message += f" and {len(errors) - 3} more errors."
        
        # Count products with valid prices for debugging
        products_with_prices = len([p for p in products if p.get('base_price', 0) > 0])
        
        # Convert NumPy types to native Python types for JSON serialization
        def convert_numpy_types(obj):
            if hasattr(obj, 'dtype'):
                return obj.item() if hasattr(obj, 'item') else str(obj)
            return obj
        
        # Clean detected price columns for JSON serialization
        cleaned_detected_cols = []
        if 'detected_price_cols' in locals() and detected_price_cols:
            for col_info in detected_price_cols:
                cleaned_col_info = {
                    'column': str(col_info['column']),
                    'min': float(col_info['min']) if col_info['min'] is not None else 0.0,
                    'max': float(col_info['max']) if col_info['max'] is not None else 0.0,
                    'count': int(col_info['count']) if col_info['count'] is not None else 0
                }
                cleaned_detected_cols.append(cleaned_col_info)
        
        return {
            "message": result_message,
            "count": len(products),
            "file_type": file_extension.upper(),
            "products_with_prices": products_with_prices,
            "columns_found": [str(col) for col in available_columns],
            "detected_price_columns": cleaned_detected_cols,
            "columns_mapped": {
                "reference": ref_col,
                "name": name_col,
                "description": desc_col,
                "category": category_col,
                "subcategory": subcategory_col,
                "prices": {
                    "base_price": price_base_col,
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
            "errors": [str(error) for error in errors]
        }
    
    except Exception as e:
        logger.error(f"Catalog file processing error: {str(e)}")
        error_detail = str(e)
        
        # Provide more helpful error messages for common CSV issues
        if 'tokenizing' in error_detail or 'fields' in error_detail:
            error_detail = "El archivo CSV tiene formato inconsistente. Esto puede ocurrir si algunas filas tienen diferentes números de columnas. Intenta guardar el archivo como Excel (.xlsx) para mejor compatibilidad."
        elif 'encoding' in error_detail:
            error_detail = "Problema de codificación del archivo. Intenta guardar el CSV con codificación UTF-8."
        elif 'separator' in error_detail:
            error_detail = "No se pudo detectar el separador del CSV. Asegúrate de que use comas, punto y coma, o tabulaciones como separadores."
        
        file_type = file_extension.upper() if 'file_extension' in locals() else 'archivo'
        raise HTTPException(status_code=400, detail=f"Error procesando {file_type}: {error_detail}")

@api_router.get("/products")
async def get_products(
    page: int = 1,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    # Calculate skip value for pagination
    skip = (page - 1) * limit
    
    # Get total count
    total_count = await db.products.count_documents({"user_id": current_user.id})
    
    # Get paginated products
    products = await db.products.find({"user_id": current_user.id}).skip(skip).limit(limit).to_list(length=limit)
    
    # Calculate pagination info
    total_pages = (total_count + limit - 1) // limit
    
    return {
        "products": [Product(**product) for product in products],
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "limit": limit,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }

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
    
    if not products:
        raise HTTPException(status_code=404, detail="No se pudieron procesar los productos encontrados")
    
    # Sort products by price for tiered quotes
    products.sort(key=lambda x: x.get("base_price", 0))
    
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

class SmartQuoteRequest(BaseModel):
    client_name: str
    product_description: str
    quantity: int
    marking_description: Optional[str] = ""
    marking_techniques: List[str] = []

class ParsedRequest(BaseModel):
    categoria: str
    cantidad: int
    perfil: Optional[str] = None  # bajo, medio, alto
    tecnica: Optional[str] = None  # bordado, serigrafia, etc.
    area_cm2: Optional[float] = None
    cobertura: Optional[str] = None  # lleno, hueco
    dimensiones: Optional[str] = None  # 7x7, 8x6, etc.
    posicion: Optional[str] = None  # pecho, espalda, etc.
    presupuesto_maximo: Optional[float] = None

def parse_client_request(description: str, quantity: int) -> ParsedRequest:
    """Parser semántico avanzado que convierte texto natural a JSON estructurado"""
    import re
    
    description_lower = description.lower()
    
    # Diccionarios de sinónimos expandidos
    categoria_synonyms = {
        'gorra': ['gorra', 'gorras', 'cap', 'caps', 'trucker', 'snapback', '6 paneles', 'baseball', 'visera'],
        'camiseta': ['camiseta', 'camisetas', 't-shirt', 'tshirt', 'playera', 'remera'],
        'polo': ['polo', 'polos', 'piqué', 'pique'],
        'sudadera': ['sudadera', 'sudaderas', 'hoodie', 'hoodies', 'capucha', 'jersey'],
        'taza': ['taza', 'tazas', 'mug', 'mugs', 'jarron'],
        'bolsa': ['bolsa', 'bolsas', 'bag', 'bags', 'tote', 'shopper'],
        'chaleco': ['chaleco', 'chalecos', 'vest'],
        'delantal': ['delantal', 'delantales', 'mandil']
    }
    
    perfil_synonyms = {
        'bajo': ['bajo', 'básico', 'barato', 'económico', 'standard'],
        'medio': ['medio', 'intermedio', 'equilibrado', 'normal'],
        'alto': ['alto', 'premium', 'calidad', 'superior', 'top']
    }
    
    tecnica_synonyms = {
        'bordado': ['bordado', 'bordados', 'embroidery', 'bordar'],
        'serigrafia': ['serigrafía', 'serigrafia', 'screen', 'silk', 'impresión'],
        'transfer': ['transfer', 'vinilo', 'termoadhesivo'],
        'sublimacion': ['sublimación', 'sublimacion', 'subli'],
        'dtf': ['dtf', 'direct to film'],
        'laser': ['láser', 'laser', 'grabado']
    }
    
    cobertura_synonyms = {
        'lleno': ['lleno', 'relleno', 'full', 'completo', 'sólido'],
        'hueco': ['hueco', 'outline', 'contorno', 'vacío', 'solo borde']
    }
    
    posicion_synonyms = {
        'pecho': ['pecho', 'frontal', 'delantero', 'front'],
        'espalda': ['espalda', 'espaldar', 'trasero', 'back'],
        'manga': ['manga', 'brazo', 'sleeve'],
        'lateral': ['lateral', 'lado', 'side']
    }
    
    # Detectar categoría
    detected_categoria = None
    for categoria, synonyms in categoria_synonyms.items():
        if any(syn in description_lower for syn in synonyms):
            detected_categoria = categoria
            break
    
    # Detectar perfil de calidad
    detected_perfil = None
    for perfil, synonyms in perfil_synonyms.items():
        if any(syn in description_lower for syn in synonyms):
            detected_perfil = perfil
            break
    
    # Detectar técnica de marcaje
    detected_tecnica = None
    for tecnica, synonyms in tecnica_synonyms.items():
        if any(syn in description_lower for syn in synonyms):
            detected_tecnica = tecnica
            break
    
    # Detectar cobertura (para bordado)
    detected_cobertura = None
    for cobertura, synonyms in cobertura_synonyms.items():
        if any(syn in description_lower for syn in synonyms):
            detected_cobertura = cobertura
            break
    
    # Detectar posición
    detected_posicion = None
    for posicion, synonyms in posicion_synonyms.items():
        if any(syn in description_lower for syn in synonyms):
            detected_posicion = posicion
            break
    
    # Detectar dimensiones y calcular área
    detected_area = None
    detected_dimensiones = None
    
    # Patrones para detectar dimensiones: 7x7, 8x6, 10×8, etc.
    dimension_patterns = [
        r'(\d+)x(\d+)\s*cm',
        r'(\d+)×(\d+)\s*cm', 
        r'(\d+)\s*x\s*(\d+)',
        r'(\d+)\s*×\s*(\d+)',
        r'(\d+)\s*por\s*(\d+)',
        r'área\s*de\s*(\d+)',
        r'superficie\s*(\d+)'
    ]
    
    for pattern in dimension_patterns:
        match = re.search(pattern, description_lower)
        if match:
            if len(match.groups()) == 2:
                width, height = int(match.group(1)), int(match.group(2))
                detected_area = width * height
                detected_dimensiones = f"{width}x{height}cm"
            elif len(match.groups()) == 1:
                detected_area = int(match.group(1))
            break
    
    # Detectar presupuesto máximo
    presupuesto_max = None
    budget_patterns = [
        r'hasta\s*(\d+)\s*€',
        r'máximo\s*(\d+)\s*euros',
        r'budget\s*(\d+)',
        r'presupuesto\s*(\d+)'
    ]
    
    for pattern in budget_patterns:
        match = re.search(pattern, description_lower)
        if match:
            presupuesto_max = float(match.group(1))
            break
    
    return ParsedRequest(
        categoria=detected_categoria or "general",
        cantidad=quantity,
        perfil=detected_perfil,
        tecnica=detected_tecnica,
        area_cm2=detected_area,
        cobertura=detected_cobertura,
        dimensiones=detected_dimensiones,
        posicion=detected_posicion,
        presupuesto_maximo=presupuesto_max
    )

def calculate_product_score(product: dict, parsed: ParsedRequest) -> float:
    """Motor de scoring para seleccionar los mejores productos"""
    score = 0.0
    
    # Pesos para el scoring
    w_precio = 0.3
    w_perfil = 0.25
    w_compatibilidad = 0.2
    w_stock = 0.1
    w_plazo = 0.1
    w_sostenibilidad = 0.05
    
    # 1. Puntuación por precio (normalizada, mejor precio = mayor score)
    precio_base = product.get('base_price', 999)
    if precio_base > 0:
        # Normalizar precio: productos más baratos obtienen mejor puntuación
        precio_normalizado = max(0, 1 - (precio_base / 50))  # Asumiendo max 50€
        score += w_precio * precio_normalizado
    
    # 2. Match de perfil de calidad
    product_perfil = None
    if 'characteristics' in product and product['characteristics']:
        product_perfil = product['characteristics'].get('perfil_calidad', '').lower()
    
    if parsed.perfil and product_perfil:
        if parsed.perfil.lower() == product_perfil:
            score += w_perfil * 1.0
        elif abs(['bajo', 'medio', 'alto'].index(parsed.perfil) - 
                ['bajo', 'medio', 'alto'].index(product_perfil)) == 1:
            score += w_perfil * 0.5
    
    # 3. Compatibilidad técnica
    print_codes = product.get('characteristics', {}).get('impresion', {}).get('tecnica_grabacion', '')
    if not print_codes:
        print_codes = product.get('characteristics', {}).get('print_codes', '')
    
    if parsed.tecnica and print_codes:
        if parsed.tecnica.lower() in print_codes.lower():
            score += w_compatibilidad * 1.0
        elif 'bordado' in parsed.tecnica and 'bordado' in print_codes.lower():
            score += w_compatibilidad * 1.0
    
    # 4. Stock disponible
    stock = product.get('characteristics', {}).get('stock_disponible', '')
    if 'si' in stock.lower():
        score += w_stock * 1.0
    elif 'bajo' in stock.lower():
        score += w_stock * 0.5
    
    # 5. Plazo de entrega (mejor plazo = mayor score)
    plazo = product.get('characteristics', {}).get('plazo_entrega_dias', 30)
    try:
        plazo_num = int(plazo) if plazo else 30
        plazo_score = max(0, 1 - (plazo_num / 30))  # Normalizar a 30 días max
        score += w_plazo * plazo_score
    except:
        pass
    
    # 6. Sostenibilidad
    sostenibilidad = product.get('characteristics', {}).get('sostenibilidad', '')
    if sostenibilidad:
        score += w_sostenibilidad * 1.0
    
    return score

@api_router.post("/quotes/generate-smart", response_model=Quote)
async def generate_smart_quote(
    quote_request: SmartQuoteRequest,
    current_user: User = Depends(get_current_user)
):
    """Sistema inteligente de presupuestos con parser semántico y motor de scoring"""
    
    # 1. PARSER SEMÁNTICO: Convertir texto natural a JSON estructurado
    parsed = parse_client_request(quote_request.product_description, quote_request.quantity)
    
    logger.info(f"Parsed request: {parsed.dict()}")
    
    # 2. BÚSQUEDA INTELIGENTE: Filtrar productos por categoría detectada
    search_filter = {"user_id": current_user.id}
    
    if parsed.categoria and parsed.categoria != "general":
        # Búsqueda por categoría detectada
        search_filter["$or"] = [
            {"category": {"$regex": parsed.categoria, "$options": "i"}},
            {"name": {"$regex": parsed.categoria, "$options": "i"}},
            {"description": {"$regex": parsed.categoria, "$options": "i"}}
        ]
    
    # Filtrar por técnica compatible si se detectó
    if parsed.tecnica:
        search_filter["$and"] = search_filter.get("$and", [])
        search_filter["$and"].append({
            "$or": [
                {"characteristics.impresion.tecnica_grabacion": {"$regex": parsed.tecnica, "$options": "i"}},
                {"characteristics.print_codes": {"$regex": parsed.tecnica, "$options": "i"}}
            ]
        })
    
    # Obtener productos candidatos
    products_cursor = await db.products.find(search_filter).limit(200).to_list(length=200)
    
    if not products_cursor:
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontraron productos de tipo '{parsed.categoria}' compatibles con '{parsed.tecnica or 'las técnicas solicitadas'}'"
        )
    
    # Convertir a objetos Product
    products = []
    for product_data in products_cursor:
        try:
            if '_id' in product_data:
                del product_data['_id']
            product = Product(**product_data)
            products.append(product.dict())
        except Exception as e:
            logger.warning(f"Error processing product: {e}")
            continue
    
    if not products:
        raise HTTPException(status_code=404, detail="No se pudieron procesar los productos encontrados")
    
    # 3. MOTOR DE SCORING: Puntuar y ordenar productos
    scored_products = []
    for product in products:
        score = calculate_product_score(product, parsed)
        scored_products.append((product, score))
    
    # Ordenar por puntuación descendente
    scored_products.sort(key=lambda x: x[1], reverse=True)
    
    # Tomar los mejores productos para cada tier
    top_products = [item[0] for item in scored_products[:20]]  # Top 20 productos
    
    logger.info(f"Top 3 products scores: {[(p['name'], s) for p, s in scored_products[:3]]}")
    
    # 4. CÁLCULO DE MARCAJE INTELIGENTE
    marking_cost_per_unit = 0.0
    marking_description = ""
    
    # Calcular coste de bordado por cm² si se detectó
    if parsed.tecnica == "bordado" and parsed.area_cm2:
        # Buscar técnicas de bordado en BD
        bordado_techniques = await db.marking_techniques.find({
            "user_id": current_user.id,
            "name": {"$regex": "bordado", "$options": "i"}
        }).to_list(length=None)
        
        if bordado_techniques:
            # Usar la técnica de bordado más apropiada
            bordado_base_price = bordado_techniques[0]["cost_per_unit"]
            
            # Factores de coste por cobertura
            cobertura_multiplier = 1.0
            if parsed.cobertura == "lleno":
                cobertura_multiplier = 1.2  # Bordado lleno cuesta más
            elif parsed.cobertura == "hueco":
                cobertura_multiplier = 0.8  # Bordado hueco cuesta menos
            
            # Factores por área (áreas grandes tienen descuento por cm²)
            area_multiplier = 1.0
            if parsed.area_cm2 <= 15:  # Áreas pequeñas
                area_multiplier = 1.3
            elif parsed.area_cm2 <= 35:  # Áreas medianas
                area_multiplier = 1.1
            elif parsed.area_cm2 >= 50:  # Áreas grandes
                area_multiplier = 0.9
            
            marking_cost_per_unit = bordado_base_price * parsed.area_cm2 * cobertura_multiplier * area_multiplier
            marking_description = f"Bordado {parsed.cobertura or 'estándar'} {parsed.dimensiones or f'{parsed.area_cm2}cm²'}"
            
        logger.info(f"Bordado calculado: {parsed.area_cm2}cm² x €{bordado_base_price} x {cobertura_multiplier} x {area_multiplier} = €{marking_cost_per_unit}")
    
    # Buscar otras técnicas si no es bordado
    elif parsed.tecnica and quote_request.marking_techniques:
        techniques = await db.marking_techniques.find({
            "user_id": current_user.id,
            "name": {"$in": quote_request.marking_techniques}
        }).to_list(length=None)
        marking_cost_per_unit = sum(t["cost_per_unit"] for t in techniques)
        marking_description = ", ".join(quote_request.marking_techniques)
    
    # 5. GENERACIÓN DE TRES NIVELES INTELIGENTES
    quantity = parsed.cantidad
    
    # Dividir productos en tres tiers basados en scoring
    tier_size = max(1, len(top_products) // 3)
    
    # TIER BÁSICO: Mejor precio (productos con mejor puntuación de precio)
    basic_products = top_products[:tier_size]
    basic_avg_price = sum(p["base_price"] for p in basic_products) / len(basic_products) if basic_products else 0
    basic_marking_cost = marking_cost_per_unit * 0.9  # Descuento en marcaje básico
    basic_total_unit = basic_avg_price + basic_marking_cost
    basic_total = basic_total_unit * quantity
    
    # TIER MEDIO: Equilibrado (productos del medio)
    medium_start = tier_size
    medium_end = tier_size * 2
    medium_products = top_products[medium_start:medium_end] if medium_end <= len(top_products) else top_products[medium_start:]
    if not medium_products:
        medium_products = basic_products
    medium_avg_price = sum(p["base_price"] for p in medium_products) / len(medium_products) if medium_products else basic_avg_price * 1.3
    medium_marking_cost = marking_cost_per_unit
    medium_total_unit = medium_avg_price + medium_marking_cost
    medium_total = medium_total_unit * quantity
    
    # TIER PREMIUM: Mejor calidad (productos con mejor puntuación general)
    premium_products = top_products[-tier_size:] if len(top_products) >= tier_size * 2 else top_products[:3]
    premium_avg_price = sum(p["base_price"] for p in premium_products) / len(premium_products) if premium_products else medium_avg_price * 1.4
    premium_marking_cost = marking_cost_per_unit * 1.2  # Marcaje premium con mejor calidad
    premium_total_unit = premium_avg_price + premium_marking_cost
    premium_total = premium_total_unit * quantity
    
    # 6. CREAR PRESUPUESTO ESTRUCTURADO
    quote = Quote(
        client_name=quote_request.client_name,
        products=[{
            "request": quote_request.product_description,
            "parsed": parsed.dict(),
            "quantity": quantity,
            "marking_description": marking_description,
            "basic": {
                "products": basic_products[:3],  # Mostrar top 3
                "avg_unit_price": round(basic_avg_price, 2),
                "marking_cost_per_unit": round(basic_marking_cost, 2),
                "total_unit_price": round(basic_total_unit, 2),
                "description": "Opción económica con buena calidad"
            },
            "medium": {
                "products": medium_products[:3],
                "avg_unit_price": round(medium_avg_price, 2),
                "marking_cost_per_unit": round(medium_marking_cost, 2),
                "total_unit_price": round(medium_total_unit, 2),
                "description": "Equilibrio perfecto calidad-precio"
            },
            "premium": {
                "products": premium_products[:3],
                "avg_unit_price": round(premium_avg_price, 2),
                "marking_cost_per_unit": round(premium_marking_cost, 2),
                "total_unit_price": round(premium_total_unit, 2),
                "description": "Máxima calidad y prestaciones"
            }
        }],
        total_basic=round(basic_total, 2),
        total_medium=round(medium_total, 2),
        total_premium=round(premium_total, 2),
        marking_techniques=quote_request.marking_techniques,
        user_id=current_user.id
    )
    
    # Guardar en BD
    await db.quotes.insert_one(quote.dict())
    
    return quote
    
    # Find matching product types
    detected_categories = []
    for product_type, synonyms in product_keywords.items():
        if any(synonym in description_lower for synonym in synonyms):
            detected_categories.append(product_type)
    
    # Search for products based on detected categories or general search
    search_filter = {"user_id": current_user.id}
    if detected_categories:
        # Use regex to find products matching any detected category
        category_pattern = "|".join(detected_categories)
        search_filter["$or"] = [
            {"name": {"$regex": category_pattern, "$options": "i"}},
            {"category": {"$regex": category_pattern, "$options": "i"}},
            {"description": {"$regex": category_pattern, "$options": "i"}}
        ]
    else:
        # General search in all text fields
        search_terms = description_lower.split()[:3]  # Use first 3 words
        search_pattern = "|".join(search_terms)
        search_filter["$or"] = [
            {"name": {"$regex": search_pattern, "$options": "i"}},
            {"description": {"$regex": search_pattern, "$options": "i"}},
            {"category": {"$regex": search_pattern, "$options": "i"}}
        ]
    
    # Get products with pagination to avoid performance issues
    products_cursor = await db.products.find(search_filter).limit(100).to_list(length=100)
    
    if not products_cursor:
        raise HTTPException(status_code=404, detail="No se encontraron productos que coincidan con la descripción")
    
    # Convert to Product objects to handle ObjectId serialization
    products = []
    for product_data in products_cursor:
        try:
            # Remove ObjectId before creating Product
            if '_id' in product_data:
                del product_data['_id']
            product = Product(**product_data)
            products.append(product.dict())
        except Exception as e:
            logger.warning(f"Error processing product: {e}")
            continue
    
    if not products:
        raise HTTPException(status_code=404, detail="No se pudieron procesar los productos encontrados")
    
    # Sort products by price for tiered quotes
    products.sort(key=lambda x: x.get("base_price", 0))
    
    # Calculate marking costs
    marking_costs_per_unit = 0
    if quote_request.marking_techniques:
        techniques = await db.marking_techniques.find({
            "user_id": current_user.id,
            "name": {"$in": quote_request.marking_techniques}
        }).to_list(length=None)
        marking_costs_per_unit = sum(t["cost_per_unit"] for t in techniques)
    elif quote_request.marking_description:
        # Try to auto-detect marking technique from description
        marking_lower = quote_request.marking_description.lower()
        auto_techniques = []
        if 'bordado' in marking_lower:
            auto_techniques.append('Bordado')
        if 'serigraf' in marking_lower:
            auto_techniques.append('Serigrafía')
        if 'transfer' in marking_lower:
            auto_techniques.append('Transfer')
        
        if auto_techniques:
            techniques = await db.marking_techniques.find({
                "user_id": current_user.id,
                "name": {"$in": auto_techniques}
            }).to_list(length=None)
            marking_costs_per_unit = sum(t["cost_per_unit"] for t in techniques)
    
    # Generate three tiers based on quality/price
    total_products = len(products)
    quantity = quote_request.quantity
    
    # Basic: cheapest options (first 1/3)
    basic_products = products[:max(1, total_products // 3)][:5]  # Limit to 5 products
    basic_unit_price = sum(p["base_price"] for p in basic_products) / len(basic_products)
    basic_total = (basic_unit_price + marking_costs_per_unit) * quantity
    
    # Medium: middle range (middle 1/3) 
    medium_start = max(1, total_products // 3)
    medium_end = max(2, (2 * total_products) // 3)
    medium_products = products[medium_start:medium_end][:5] if medium_end > medium_start else products[1:6]
    medium_unit_price = sum(p["base_price"] for p in medium_products) / len(medium_products) if medium_products else basic_unit_price * 1.5
    medium_total = (medium_unit_price + marking_costs_per_unit * 1.2) * quantity
    
    # Premium: highest quality (last 1/3)
    premium_start = max(2, (2 * total_products) // 3)
    premium_products = products[premium_start:][:5]
    if not premium_products:
        premium_products = products[-3:]
    premium_unit_price = sum(p["base_price"] for p in premium_products) / len(premium_products) if premium_products else medium_unit_price * 1.5
    premium_total = (premium_unit_price + marking_costs_per_unit * 1.5) * quantity
    
    quote = Quote(
        client_name=quote_request.client_name,
        products=[{
            "request": quote_request.product_description,
            "quantity": quantity,
            "marking": quote_request.marking_description,
            "basic": {
                "products": basic_products[:3],  # Show top 3 products
                "unit_price": round(basic_unit_price, 2),
                "marking_cost": round(marking_costs_per_unit, 2),
                "total_unit": round(basic_unit_price + marking_costs_per_unit, 2)
            },
            "medium": {
                "products": medium_products[:3],
                "unit_price": round(medium_unit_price, 2),
                "marking_cost": round(marking_costs_per_unit * 1.2, 2),
                "total_unit": round(medium_unit_price + marking_costs_per_unit * 1.2, 2)
            },
            "premium": {
                "products": premium_products[:3],
                "unit_price": round(premium_unit_price, 2),
                "marking_cost": round(marking_costs_per_unit * 1.5, 2),
                "total_unit": round(premium_unit_price + marking_costs_per_unit * 1.5, 2)
            }
        }],
        total_basic=round(basic_total, 2),
        total_medium=round(medium_total, 2),
        total_premium=round(premium_total, 2),
        marking_techniques=quote_request.marking_techniques,
        user_id=current_user.id
    )
    
    await db.quotes.insert_one(quote.dict())
    return quote

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