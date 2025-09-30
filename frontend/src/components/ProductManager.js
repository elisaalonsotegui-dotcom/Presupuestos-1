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

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
              <p className="text-sm text-blue-700 font-medium mb-2">El sistema acepta múltiples formatos de Excel:</p>
              <ul className="text-xs text-blue-600 space-y-1">
                <li>• <strong>Nombres</strong>: nombre, producto, articulo, item, name</li>
                <li>• <strong>Descripción</strong>: descripcion, description, desc, detalle</li>
                <li>• <strong>Precio</strong>: precio, price, coste, cost, pvp, tarifa</li>
                <li>• <strong>Categoría</strong>: categoria, category, tipo, clase, familia</li>
                <li>• <strong>Otras columnas</strong> se guardan como características</li>
              </ul>
              <p className="text-xs text-blue-500 mt-2">
                💡 El sistema detecta automáticamente las columnas de tu Excel
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
                <Button className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="add-product-button">
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
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((product) => (
                    <TableRow key={product.id} data-testid="product-row">
                      <TableCell className="font-medium">{product.name}</TableCell>
                      <TableCell className="max-w-xs">
                        <div className="truncate" title={product.description}>
                          {product.description || 'Sin descripción'}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Euro className="w-4 h-4 text-gray-400" />
                          <span className="font-medium">{product.base_price.toFixed(2)}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Tag className="w-4 h-4 text-gray-400" />
                          <span>{product.category || 'Sin categoría'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-xs">
                          {Object.keys(product.characteristics).length > 0 ? (
                            <div className="text-xs text-gray-600">
                              {Object.entries(product.characteristics).slice(0, 2).map(([key, value]) => (
                                <div key={key}>{key}: {String(value)}</div>
                              ))}
                              {Object.keys(product.characteristics).length > 2 && (
                                <div className="text-gray-400">+{Object.keys(product.characteristics).length - 2} más</div>
                              )}
                            </div>
                          ) : (
                            <span className="text-gray-400 text-xs">Sin características</span>
                          )}
                        </div>
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