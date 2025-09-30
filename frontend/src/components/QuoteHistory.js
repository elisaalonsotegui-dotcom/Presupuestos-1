import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { toast } from 'sonner';
import { History, FileText, Euro, Calendar, User, Eye, Download } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const QuoteHistory = () => {
  const [quotes, setQuotes] = useState([]);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQuotes();
  }, []);

  const fetchQuotes = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/quotes`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setQuotes(response.data);
    } catch (error) {
      console.error('Error fetching quotes:', error);
      toast.error('Error al cargar historial de presupuestos');
    } finally {
      setLoading(false);
    }
  };

  const handleViewQuote = async (quoteId) => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/quotes/${quoteId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedQuote(response.data);
      setIsDetailOpen(true);
    } catch (error) {
      console.error('Error fetching quote details:', error);
      toast.error('Error al cargar detalles del presupuesto');
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
      case 'basic': return 'bg-green-100 text-green-800';
      case 'medium': return 'bg-blue-100 text-blue-800';
      case 'premium': return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Historial de Presupuestos</h1>
        <p className="text-gray-600">
          Consulta y gestiona todos los presupuestos generados anteriormente.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total presupuestos</p>
                <p className="text-2xl font-bold text-gray-900">{quotes.length}</p>
              </div>
              <FileText className="w-8 h-8 text-emerald-600" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Valor total básico</p>
                <p className="text-2xl font-bold text-green-700">
                  €{quotes.reduce((sum, q) => sum + q.total_basic, 0).toFixed(0)}
                </p>
              </div>
              <Euro className="w-8 h-8 text-green-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Valor total premium</p>
                <p className="text-2xl font-bold text-purple-700">
                  €{quotes.reduce((sum, q) => sum + q.total_premium, 0).toFixed(0)}
                </p>
              </div>
              <Euro className="w-8 h-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Clientes únicos</p>
                <p className="text-2xl font-bold text-gray-900">
                  {[...new Set(quotes.map(q => q.client_name))].length}
                </p>
              </div>
              <User className="w-8 h-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quotes Table */}
      <Card className="border-0 bg-white/90 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <History className="w-5 h-5 text-emerald-600" />
            <span>Presupuestos Generados</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {quotes.length === 0 ? (
            <div className="text-center py-12">
              <History className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No hay presupuestos</h3>
              <p className="text-gray-500 mb-4">
                Aún no has generado ningún presupuesto. Crea tu primer presupuesto para verlo aquí.
              </p>
              <Button 
                onClick={() => window.location.href = '/quotes'} 
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                Crear Presupuesto
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-semibold">Cliente</TableHead>
                    <TableHead className="font-semibold">Fecha</TableHead>
                    <TableHead className="font-semibold">Básico</TableHead>
                    <TableHead className="font-semibold">Medio</TableHead>
                    <TableHead className="font-semibold">Premium</TableHead>
                    <TableHead className="font-semibold">Técnicas</TableHead>
                    <TableHead className="font-semibold">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {quotes.map((quote) => (
                    <TableRow key={quote.id} data-testid="quote-row">
                      <TableCell className="font-medium">
                        <div className="flex items-center space-x-2">
                          <User className="w-4 h-4 text-gray-400" />
                          <span>{quote.client_name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4 text-gray-400" />
                          <span className="text-sm">
                            {new Date(quote.created_at).toLocaleDateString('es-ES')}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Euro className="w-4 h-4 text-green-600" />
                          <span className="font-medium text-green-700">
                            {quote.total_basic.toFixed(2)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Euro className="w-4 h-4 text-blue-600" />
                          <span className="font-medium text-blue-700">
                            {quote.total_medium.toFixed(2)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Euro className="w-4 h-4 text-purple-600" />
                          <span className="font-medium text-purple-700">
                            {quote.total_premium.toFixed(2)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {quote.marking_techniques.slice(0, 2).map((technique) => (
                            <Badge key={technique} variant="secondary" className="text-xs">
                              {technique}
                            </Badge>
                          ))}
                          {quote.marking_techniques.length > 2 && (
                            <Badge variant="secondary" className="text-xs">
                              +{quote.marking_techniques.length - 2}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleViewQuote(quote.id)}
                            data-testid={`view-quote-${quote.id}`}
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => toast.success('Función de exportación próximamente')}
                            data-testid={`export-quote-${quote.id}`}
                          >
                            <Download className="w-4 h-4" />
                          </Button>
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

      {/* Quote Detail Dialog */}
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <FileText className="w-5 h-5 text-emerald-600" />
              <span>Detalles del Presupuesto</span>
            </DialogTitle>
          </DialogHeader>
          
          {selectedQuote && (
            <div className="space-y-6">
              {/* Client Info */}
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium mb-2">Información del Cliente</h3>
                <p className="text-sm text-gray-600">
                  <strong>Cliente:</strong> {selectedQuote.client_name}
                </p>
                <p className="text-sm text-gray-600">
                  <strong>Fecha:</strong> {new Date(selectedQuote.created_at).toLocaleDateString('es-ES')}
                </p>
              </div>

              {/* Price Tiers */}
              <div className="grid grid-cols-1 gap-4">
                {[
                  { tier: 'basic', total: selectedQuote.total_basic, label: 'Básico' },
                  { tier: 'medium', total: selectedQuote.total_medium, label: 'Medio' },
                  { tier: 'premium', total: selectedQuote.total_premium, label: 'Premium' }
                ].map(({ tier, total, label }) => (
                  <div key={tier} className={`p-4 border rounded-lg ${getTierColor(tier)}`}>
                    <div className="flex items-center justify-between">
                      <div className="font-semibold">{label}</div>
                      <div className="flex items-center space-x-1">
                        <Euro className="w-4 h-4" />
                        <span className="text-lg font-bold">{total.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Marking Techniques */}
              {selectedQuote.marking_techniques.length > 0 && (
                <div className="bg-emerald-50 p-4 rounded-lg">
                  <h4 className="font-medium text-emerald-800 mb-2">Técnicas de marcaje</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedQuote.marking_techniques.map((technique) => (
                      <Badge key={technique} className="bg-emerald-200 text-emerald-800">
                        {technique}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Products */}
              {selectedQuote.products && selectedQuote.products[0] && (
                <div className="space-y-4">
                  <h4 className="font-medium">Productos incluidos</h4>
                  {Object.entries(selectedQuote.products[0]).map(([tier, products]) => (
                    <div key={tier} className="border border-gray-200 rounded-lg p-4">
                      <h5 className="font-medium mb-3 capitalize">{getTierLabel(tier)}</h5>
                      <div className="space-y-2 max-h-32 overflow-y-auto">
                        {products.map((product, index) => (
                          <div key={index} className="flex justify-between items-center text-sm">
                            <span className="truncate mr-2">{product.name}</span>
                            <span className="text-gray-600 font-medium">€{product.base_price}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="pt-4 border-t">
                <Button 
                  className="w-full" 
                  onClick={() => toast.success('Función de exportación próximamente')}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Exportar Presupuesto a PDF
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default QuoteHistory;