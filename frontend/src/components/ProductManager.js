import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { toast } from 'sonner';
import { Upload, Package, Plus, Euro, Tag, FileText, Trash2, AlertTriangle } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ProductManager = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newProduct, setNewProduct] = useState({
    name: '',
    description: '',
    base_price: '',
    category: '',
    characteristics: {}
  });
  const [deletingProduct, setDeletingProduct] = useState(null);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/products`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProducts(response.data);
    } catch (error) {
      console.error('Error fetching products:', error);
      toast.error('Error al cargar productos');
    }
  };

  const handleExcelUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      toast.error('Por favor sube un archivo Excel (.xlsx o .xls)');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API}/products/upload-excel`, formData, {
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });

      toast.success(`¡${response.data.count} productos subidos exitosamente!`);
      fetchProducts();
    } catch (error) {
      console.error('Error uploading Excel:', error);
      toast.error(error.response?.data?.detail || 'Error al subir el archivo');
    } finally {
      setLoading(false);
      event.target.value = '';
    }
  };

  const handleCreateProduct = async () => {
    if (!newProduct.name || !newProduct.base_price) {
      toast.error('Nombre y precio son obligatorios');
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const productData = {
        ...newProduct,
        base_price: parseFloat(newProduct.base_price),
        characteristics: typeof newProduct.characteristics === 'string' 
          ? JSON.parse(newProduct.characteristics || '{}')
          : newProduct.characteristics
      };

      await axios.post(`${API}/products`, productData, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success('Producto creado exitosamente');
      setNewProduct({ name: '', description: '', base_price: '', category: '', characteristics: {} });
      setIsDialogOpen(false);
      fetchProducts();
    } catch (error) {
      console.error('Error creating product:', error);
      toast.error('Error al crear producto');
    }
  };

  const handleDeleteProduct = async (productId, productName) => {
    if (window.confirm(`¿Estás seguro de que quieres eliminar "${productName}"?`)) {
      setDeletingProduct(productId);
      try {
        const token = localStorage.getItem('token');
        await axios.delete(`${API}/products/${productId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        toast.success('Producto eliminado exitosamente');
        fetchProducts();
      } catch (error) {
        console.error('Error deleting product:', error);
        toast.error('Error al eliminar producto');
      } finally {
        setDeletingProduct(null);
      }
    }
  };

  const handleDeleteAllProducts = async () => {
    if (window.confirm('¿Estás seguro de que quieres eliminar TODOS los productos? Esta acción no se puede deshacer.')) {
      try {
        const token = localStorage.getItem('token');
        await axios.delete(`${API}/products`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        toast.success('Todos los productos han sido eliminados');
        fetchProducts();
      } catch (error) {
        console.error('Error deleting all products:', error);
        toast.error('Error al eliminar productos');
      }
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Gestión de Productos</h1>
        <p className="text-gray-600">
          Gestiona tu catálogo de productos y sube archivos Excel para importar productos en lotes.
        </p>
      </div>

      {/* Upload and Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Upload className="w-5 h-5 text-emerald-600" />
              <span>Subir Excel</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="upload-area">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleExcelUpload}
                className="hidden"
                id="excel-upload"
                data-testid="excel-file-input"
              />
              <label htmlFor="excel-upload" className="cursor-pointer block">
                <div className="text-center py-6">
                  <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-sm text-gray-600 mb-2">
                    Haz clic para seleccionar un archivo Excel
                  </p>
                  <p className="text-xs text-gray-400">
                    Formatos: .xlsx, .xls
                  </p>
                </div>
              </label>
            </div>
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-blue-700 font-medium mb-2">Formato estándar de proveedor - Columnas reconocidas:</p>
              <div className="grid grid-cols-2 gap-4 text-xs text-blue-600">
                <div>
                  <p className="font-medium">Información básica:</p>
                  <ul className="space-y-1">
                    <li>• REF. / Referencia</li>
                    <li>• ARTÍCULO / Producto</li>
                    <li>• DESCRIPCIÓN</li>
                    <li>• CATEGORÍA</li>
                    <li>• SUBCATEGORÍA</li>
                  </ul>
                </div>
                <div>
                  <p className="font-medium">Dimensiones y precios:</p>
                  <ul className="space-y-1">
                    <li>• PROFUNDIDAD, PESO, ANCHO, ALTO</li>
                    <li>• -500, +500, +2000, +5000 (precios)</li>
                    <li>• PRINT CODE / TÉCNICA DE GRABACIÓN</li>
                    <li>• MEDIDA MÁXIMA DE GRABACIÓN</li>
                  </ul>
                </div>
              </div>
              <p className="text-xs text-blue-500 mt-2">
                💡 El sistema detecta automáticamente las columnas y maneja precios por volumen
              </p>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <p className="text-sm text-green-700 font-medium mb-3">📥 Descargar Plantillas Excel:</p>
              <div className="space-y-2">
                <a 
                  href={`${BACKEND_URL}/api/download/plantilla-proveedor`}
                  download
                  className="block w-full text-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm"
                >
                  📋 Descargar Plantilla Proveedor 2025
                </a>
                <a 
                  href={`${BACKEND_URL}/api/download/plantilla-vacia`}
                  download
                  className="block w-full text-center px-4 py-2 bg-green-100 text-green-800 rounded-md hover:bg-green-200 transition-colors text-sm"
                >
                  📄 Descargar Plantilla Vacía
                </a>
                <a 
                  href={`${BACKEND_URL}/api/download/plantilla-simple`}
                  download
                  className="block w-full text-center px-4 py-2 bg-blue-100 text-blue-800 rounded-md hover:bg-blue-200 transition-colors text-sm"
                >
                  📑 Descargar Plantilla Simple (básica)
                </a>
              </div>
              <p className="text-xs text-green-600 mt-2">
                💡 Usa estas plantillas para estandarizar tus archivos de proveedores
              </p>
            </div>
            {loading && (
              <div className="flex items-center justify-center py-4">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-emerald-600"></div>
                <span className="ml-2 text-sm text-gray-600">Procesando archivo...</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Package className="w-5 h-5 text-emerald-600" />
                <span>Resumen</span>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-emerald-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-emerald-700">{products.length}</div>
                <div className="text-sm text-emerald-600">Total productos</div>
              </div>
              <div className="bg-blue-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-blue-700">
                  {[...new Set(products.map(p => p.category))].length}
                </div>
                <div className="text-sm text-blue-600">Categorías</div>
              </div>
            </div>
            
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button className="w-full bg-emerald-600 hover:bg-emerald-700 mb-2" data-testid="add-product-button">
                  <Plus className="w-4 h-4 mr-2" />
                  Añadir Producto Manual
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Nuevo Producto</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="name">Nombre del producto</Label>
                    <Input
                      id="name"
                      value={newProduct.name}
                      onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                      placeholder="Nombre del producto"
                      data-testid="product-name-input"
                    />
                  </div>
                  <div>
                    <Label htmlFor="description">Descripción</Label>
                    <Textarea
                      id="description"
                      value={newProduct.description}
                      onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
                      placeholder="Descripción del producto"
                      data-testid="product-description-input"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="price">Precio (€)</Label>
                      <Input
                        id="price"
                        type="number"
                        step="0.01"
                        value={newProduct.base_price}
                        onChange={(e) => setNewProduct({ ...newProduct, base_price: e.target.value })}
                        placeholder="0.00"
                        data-testid="product-price-input"
                      />
                    </div>
                    <div>
                      <Label htmlFor="category">Categoría</Label>
                      <Input
                        id="category"
                        value={newProduct.category}
                        onChange={(e) => setNewProduct({ ...newProduct, category: e.target.value })}
                        placeholder="Categoría"
                        data-testid="product-category-input"
                      />
                    </div>
                  </div>
                  <Button 
                    onClick={handleCreateProduct} 
                    className="w-full bg-emerald-600 hover:bg-emerald-700"
                    data-testid="save-product-button"
                  >
                    Crear Producto
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
            
            {products.length > 0 && (
              <Button 
                onClick={handleDeleteAllProducts}
                variant="outline"
                className="w-full text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                data-testid="delete-all-products-button"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Eliminar Todos
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Products Table */}
      <Card className="border-0 bg-white/90 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Package className="w-5 h-5 text-emerald-600" />
            <span>Catálogo de Productos</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {products.length === 0 ? (
            <div className="text-center py-12">
              <Package className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No hay productos</h3>
              <p className="text-gray-500 mb-4">
                Sube un archivo Excel o añade productos manualmente para comenzar.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-semibold">Nombre</TableHead>
                    <TableHead className="font-semibold">Descripción</TableHead>
                    <TableHead className="font-semibold">Precio</TableHead>
                    <TableHead className="font-semibold">Categoría</TableHead>
                    <TableHead className="font-semibold">Características</TableHead>
                    <TableHead className="font-semibold w-20">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((product) => (
                    <TableRow key={product.id} data-testid="product-row">
                      <TableCell className="font-medium">{product.name}</TableCell>
                      <TableCell className="max-w-xs">
                        <div className="space-y-1">
                          <div className="truncate text-sm" title={product.description}>
                            {product.description || 'Sin descripción'}
                          </div>
                          {product.characteristics?.referencia && (
                            <div className="text-xs text-blue-600 font-mono">
                              REF: {product.characteristics.referencia}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center space-x-1">
                            <Euro className="w-4 h-4 text-gray-400" />
                            <span className="font-medium">{product.base_price.toFixed(2)}</span>
                          </div>
                          {product.characteristics?.precios_volumen && (
                            <div className="text-xs text-gray-500">
                              {Object.entries(product.characteristics.precios_volumen)
                                .filter(([_, price]) => price > 0)
                                .slice(0, 2)
                                .map(([qty, price]) => (
                                  <div key={qty}>{qty}: €{price}</div>
                                ))}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center space-x-1">
                            <Tag className="w-4 h-4 text-gray-400" />
                            <span>{product.category || 'Sin categoría'}</span>
                          </div>
                          {product.characteristics?.subcategoria && (
                            <div className="text-xs text-gray-500">
                              {product.characteristics.subcategoria}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-xs text-xs">
                          {/* Mostrar dimensiones si existen */}
                          {(product.characteristics?.ancho || product.characteristics?.alto) && (
                            <div className="text-gray-600 mb-1">
                              📏 {product.characteristics?.ancho && `${product.characteristics.ancho}cm`}
                              {product.characteristics?.ancho && product.characteristics?.alto && ' × '}
                              {product.characteristics?.alto && `${product.characteristics.alto}cm`}
                            </div>
                          )}
                          
                          {/* Mostrar técnica de impresión */}
                          {product.characteristics?.impresion?.tecnica_grabacion && (
                            <div className="text-blue-600 mb-1">
                              🎨 {product.characteristics.impresion.tecnica_grabacion}
                            </div>
                          )}
                          
                          {/* Mostrar área de impresión */}
                          {product.characteristics?.impresion?.medida_maxima_grabacion && (
                            <div className="text-green-600">
                              📐 {product.characteristics.impresion.medida_maxima_grabacion}
                            </div>
                          )}
                          
                          {/* Fallback para productos sin características específicas */}
                          {!product.characteristics?.ancho && !product.characteristics?.impresion?.tecnica_grabacion && (
                            Object.keys(product.characteristics).length > 0 ? (
                              <div className="text-gray-600">
                                {Object.entries(product.characteristics).slice(0, 2).map(([key, value]) => {
                                  if (key === 'precios_volumen' || key === 'impresion' || key === 'referencia' || key === 'subcategoria') return null;
                                  return <div key={key}>{key}: {String(value)}</div>;
                                }).filter(Boolean)}
                                {Object.keys(product.characteristics).length > 4 && (
                                  <div className="text-gray-400">+más datos...</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-400">Sin características</span>
                            )
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteProduct(product.id, product.name)}
                          disabled={deletingProduct === product.id}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                          data-testid={`delete-product-${product.id}`}
                        >
                          {deletingProduct === product.id ? (
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-600"></div>
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ProductManager;