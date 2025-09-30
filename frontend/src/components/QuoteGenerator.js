import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Checkbox } from './ui/checkbox';
import { toast } from 'sonner';
import { FileText, Calculator, User, Settings, Euro, Package, TrendingUp } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const QuoteGenerator = () => {
  const [techniques, setTechniques] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [quoteData, setQuoteData] = useState({
    client_name: '',
    search_criteria: {
      category: ''
    },
    marking_techniques: []
  });
  const [generatedQuote, setGeneratedQuote] = useState(null);

  useEffect(() => {
    fetchTechniques();
    fetchCategories();
  }, []);

  const fetchTechniques = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/marking-techniques`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTechniques(response.data);
    } catch (error) {
      console.error('Error fetching techniques:', error);
    }
  };

  const fetchCategories = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/products`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const uniqueCategories = [...new Set(response.data.map(p => p.category).filter(Boolean))];
      setCategories(uniqueCategories);
    } catch (error) {
      console.error('Error fetching categories:', error);
    }
  };

  const handleTechniqueChange = (techniqueName, checked) => {
    if (checked) {
      setQuoteData({
        ...quoteData,
        marking_techniques: [...quoteData.marking_techniques, techniqueName]
      });
    } else {
      setQuoteData({
        ...quoteData,
        marking_techniques: quoteData.marking_techniques.filter(t => t !== techniqueName)
      });
    }
  };

  const handleGenerateQuote = async () => {
    if (!quoteData.client_name) {
      toast.error('Por favor ingresa el nombre del cliente');
      return;
    }

    if (!quoteData.search_criteria.category) {
      toast.error('Por favor selecciona una categoría de productos');
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API}/quotes/generate`, quoteData, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setGeneratedQuote(response.data);
      toast.success('¡Presupuesto generado exitosamente!');
    } catch (error) {
      console.error('Error generating quote:', error);
      toast.error(error.response?.data?.detail || 'Error al generar presupuesto');
    } finally {
      setLoading(false);
    }
  };

  const getTierLabel = (tier) => {
    switch (tier) {
      case 'basic': return 'Básico';
      case 'medium': return 'Medio';
      case 'premium': return 'Premium';
      default: return tier;
    }
  };

  const getTierColor = (tier) => {
    switch (tier) {
      case 'basic': return 'text-green-700 bg-green-50 border-green-200';
      case 'medium': return 'text-blue-700 bg-blue-50 border-blue-200';
      case 'premium': return 'text-purple-700 bg-purple-50 border-purple-200';
      default: return 'text-gray-700 bg-gray-50 border-gray-200';
    }
  };

  const getTierDescription = (tier) => {
    switch (tier) {
      case 'basic': return 'Productos más económicos con calidad estándar';
      case 'medium': return 'Productos de gama media con buena relación calidad-precio';
      case 'premium': return 'Productos de alta gama con máxima calidad';
      default: return '';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Generador de Presupuestos</h1>
        <p className="text-gray-600">
          Crea presupuestos automáticos con tres niveles de precios según tus criterios.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Form */}
        <div className="space-y-6">
          <Card className="border-0 bg-white/90 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <User className="w-5 h-5 text-emerald-600" />
                <span>Información del Cliente</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="client-name">Nombre del cliente</Label>
                <Input
                  id="client-name"
                  value={quoteData.client_name}
                  onChange={(e) => setQuoteData({ ...quoteData, client_name: e.target.value })}
                  placeholder="Nombre de la empresa o cliente"
                  data-testid="client-name-input"
                />
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 bg-white/90 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Package className="w-5 h-5 text-emerald-600" />
                <span>Criterios de Búsqueda</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="category">Categoría de productos</Label>
                <Select 
                  value={quoteData.search_criteria.category} 
                  onValueChange={(value) => setQuoteData({
                    ...quoteData,
                    search_criteria: { ...quoteData.search_criteria, category: value }
                  })}
                >
                  <SelectTrigger data-testid="category-select">
                    <SelectValue placeholder="Selecciona una categoría" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category} value={category}>
                        {category}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {categories.length === 0 && (
                <div className="bg-amber-50 p-4 rounded-lg">
                  <p className="text-sm text-amber-700">
                    No hay categorías disponibles. Asegúrate de tener productos cargados en el sistema.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-0 bg-white/90 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Settings className="w-5 h-5 text-emerald-600" />
                <span>Técnicas de Marcaje</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {techniques.length === 0 ? (
                <div className="bg-blue-50 p-4 rounded-lg">
                  <p className="text-sm text-blue-700">
                    No hay técnicas de marcaje configuradas. Añade técnicas para incluir sus costes en los presupuestos.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {techniques.map((technique) => (
                    <div key={technique.id} className="flex items-center space-x-3 p-3 border border-gray-100 rounded-lg">
                      <Checkbox
                        id={technique.id}
                        checked={quoteData.marking_techniques.includes(technique.name)}
                        onCheckedChange={(checked) => handleTechniqueChange(technique.name, checked)}
                        data-testid={`technique-${technique.name.toLowerCase().replace(' ', '-')}`}
                      />
                      <div className="flex-1">
                        <label htmlFor={technique.id} className="text-sm font-medium cursor-pointer">
                          {technique.name}
                        </label>
                        <div className="text-xs text-gray-500">
                          €{technique.cost_per_unit} por unidad
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Button 
            onClick={handleGenerateQuote}
            disabled={loading}
            className="w-full bg-emerald-600 hover:bg-emerald-700 h-12"
            data-testid="generate-quote-button"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Generando presupuesto...
              </>
            ) : (
              <>
                <Calculator className="w-4 h-4 mr-2" />
                Generar Presupuesto
              </>
            )}
          </Button>
        </div>

        {/* Results */}
        <div>
          {generatedQuote ? (
            <Card className="border-0 bg-white/90 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <FileText className="w-5 h-5 text-emerald-600" />
                  <span>Presupuesto Generado</span>
                </CardTitle>
                <p className="text-sm text-gray-600">Cliente: {generatedQuote.client_name}</p>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Summary Cards */}
                <div className="grid grid-cols-1 gap-4">
                  {[
                    { tier: 'basic', total: generatedQuote.total_basic },
                    { tier: 'medium', total: generatedQuote.total_medium },
                    { tier: 'premium', total: generatedQuote.total_premium }
                  ].map(({ tier, total }) => (
                    <div key={tier} className={`p-4 border rounded-lg ${getTierColor(tier)}`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-semibold">{getTierLabel(tier)}</div>
                        <div className="flex items-center space-x-1">
                          <Euro className="w-4 h-4" />
                          <span className="text-lg font-bold">{total.toFixed(2)}</span>
                        </div>
                      </div>
                      <p className="text-xs opacity-80">{getTierDescription(tier)}</p>
                    </div>
                  ))}
                </div>

                {/* Marking Techniques Used */}
                {generatedQuote.marking_techniques.length > 0 && (
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-medium text-sm mb-2">Técnicas de marcaje incluidas:</h4>
                    <div className="flex flex-wrap gap-2">
                      {generatedQuote.marking_techniques.map((technique) => (
                        <span
                          key={technique}
                          className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs rounded-full"
                        >
                          {technique}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Product Details */}
                {generatedQuote.products && generatedQuote.products[0] && (
                  <div className="space-y-4">
                    <h4 className="font-medium">Productos por nivel:</h4>
                    {Object.entries(generatedQuote.products[0]).map(([tier, products]) => (
                      <div key={tier} className="space-y-2">
                        <h5 className="text-sm font-medium text-gray-700 capitalize">{getTierLabel(tier)}</h5>
                        <div className="bg-gray-50 p-3 rounded-lg">
                          <p className="text-xs text-gray-600 mb-2">
                            {products.length} producto{products.length !== 1 ? 's' : ''} seleccionado{products.length !== 1 ? 's' : ''}
                          </p>
                          <div className="space-y-1">
                            {products.slice(0, 3).map((product, index) => (
                              <div key={index} className="flex justify-between text-xs">
                                <span className="truncate mr-2">{product.name}</span>
                                <span className="text-gray-600">€{product.base_price}</span>
                              </div>
                            ))}
                            {products.length > 3 && (
                              <p className="text-xs text-gray-500">+{products.length - 3} productos más...</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="pt-4 border-t">
                  <Button 
                    variant="outline" 
                    className="w-full"
                    onClick={() => toast.success('Función de exportación próximamente')}
                    data-testid="export-quote-button"
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    Exportar a PDF
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-0 bg-white/90 backdrop-blur-sm">
              <CardContent className="py-12">
                <div className="text-center">
                  <Calculator className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Genera tu primer presupuesto
                  </h3>
                  <p className="text-gray-500 max-w-sm mx-auto">
                    Completa la información del cliente y criterios de búsqueda para generar un presupuesto automático.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default QuoteGenerator;