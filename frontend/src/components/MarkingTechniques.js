import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { toast } from 'sonner';
import { Settings, Plus, Euro, FileText, Palette } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MarkingTechniques = () => {
  const [techniques, setTechniques] = useState([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newTechnique, setNewTechnique] = useState({
    name: '',
    cost_per_unit: '',
    description: ''
  });

  useEffect(() => {
    fetchTechniques();
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
      toast.error('Error al cargar técnicas de marcaje');
    }
  };

  const handleCreateTechnique = async () => {
    if (!newTechnique.name || !newTechnique.cost_per_unit) {
      toast.error('Nombre y coste son obligatorios');
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const techniqueData = {
        ...newTechnique,
        cost_per_unit: parseFloat(newTechnique.cost_per_unit)
      };

      await axios.post(`${API}/marking-techniques`, techniqueData, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success('Técnica de marcaje creada exitosamente');
      setNewTechnique({ name: '', cost_per_unit: '', description: '' });
      setIsDialogOpen(false);
      fetchTechniques();
    } catch (error) {
      console.error('Error creating technique:', error);
      toast.error('Error al crear técnica de marcaje');
    }
  };

  const predefinedTechniques = [
    { name: 'Bordado', cost_per_unit: 2.50, description: 'Bordado personalizado con hilo de alta calidad' },
    { name: 'Serigrafía', cost_per_unit: 1.80, description: 'Impresión serigráfica para grandes cantidades' },
    { name: 'Transfer Digital', cost_per_unit: 1.20, description: 'Impresión digital con transfer térmico' },
    { name: 'Grabado Láser', cost_per_unit: 3.00, description: 'Grabado láser de precisión en materiales diversos' },
    { name: 'Tampografía', cost_per_unit: 1.50, description: 'Impresión tampográfica para superficies irregulares' },
    { name: 'Impresión UV', cost_per_unit: 2.20, description: 'Impresión UV de alta calidad y durabilidad' }
  ];

  const handleAddPredefined = async (technique) => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/marking-techniques`, technique, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${technique.name} añadido exitosamente`);
      fetchTechniques();
    } catch (error) {
      toast.error(`Error al añadir ${technique.name}`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Técnicas de Marcaje</h1>
        <p className="text-gray-600">
          Gestiona las técnicas de marcaje disponibles y sus costes asociados para el cálculo de presupuestos.
        </p>
      </div>

      {/* Stats and Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Settings className="w-5 h-5 text-emerald-600" />
              <span>Resumen</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-emerald-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-emerald-700">{techniques.length}</div>
                <div className="text-sm text-emerald-600">Técnicas activas</div>
              </div>
              <div className="bg-blue-50 p-4 rounded-lg text-center">
                <div className="text-2xl font-bold text-blue-700">
                  €{techniques.length > 0 
                    ? (techniques.reduce((sum, t) => sum + t.cost_per_unit, 0) / techniques.length).toFixed(2) 
                    : '0.00'
                  }
                </div>
                <div className="text-sm text-blue-600">Coste promedio</div>
              </div>
            </div>
            
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button className="w-full bg-emerald-600 hover:bg-emerald-700" data-testid="add-technique-button">
                  <Plus className="w-4 h-4 mr-2" />
                  Nueva Técnica
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Nueva Técnica de Marcaje</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="technique-name">Nombre de la técnica</Label>
                    <Input
                      id="technique-name"
                      value={newTechnique.name}
                      onChange={(e) => setNewTechnique({ ...newTechnique, name: e.target.value })}
                      placeholder="Ej: Bordado, Serigrafía, etc."
                      data-testid="technique-name-input"
                    />
                  </div>
                  <div>
                    <Label htmlFor="technique-cost">Coste por unidad (€)</Label>
                    <Input
                      id="technique-cost"
                      type="number"
                      step="0.01"
                      value={newTechnique.cost_per_unit}
                      onChange={(e) => setNewTechnique({ ...newTechnique, cost_per_unit: e.target.value })}
                      placeholder="0.00"
                      data-testid="technique-cost-input"
                    />
                  </div>
                  <div>
                    <Label htmlFor="technique-description">Descripción</Label>
                    <Textarea
                      id="technique-description"
                      value={newTechnique.description}
                      onChange={(e) => setNewTechnique({ ...newTechnique, description: e.target.value })}
                      placeholder="Descripción de la técnica de marcaje"
                      data-testid="technique-description-input"
                    />
                  </div>
                  <Button 
                    onClick={handleCreateTechnique} 
                    className="w-full bg-emerald-600 hover:bg-emerald-700"
                    data-testid="save-technique-button"
                  >
                    Crear Técnica
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>

        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Palette className="w-5 h-5 text-emerald-600" />
              <span>Técnicas Predefinidas</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {predefinedTechniques.map((technique, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <div className="font-medium text-sm">{technique.name}</div>
                    <div className="text-xs text-gray-500">€{technique.cost_per_unit}</div>
                  </div>
                  <Button 
                    size="sm"
                    variant="outline"
                    onClick={() => handleAddPredefined(technique)}
                    className="text-xs"
                    data-testid={`add-predefined-${technique.name.toLowerCase().replace(' ', '-')}`}
                  >
                    Añadir
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Techniques Table */}
      <Card className="border-0 bg-white/90 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Settings className="w-5 h-5 text-emerald-600" />
            <span>Técnicas Configuradas</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {techniques.length === 0 ? (
            <div className="text-center py-12">
              <Settings className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No hay técnicas configuradas</h3>
              <p className="text-gray-500 mb-4">
                Añade técnicas de marcaje para poder calcular presupuestos completos.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-semibold">Técnica</TableHead>
                    <TableHead className="font-semibold">Coste por unidad</TableHead>
                    <TableHead className="font-semibold">Descripción</TableHead>
                    <TableHead className="font-semibold">Fecha creación</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {techniques.map((technique) => (
                    <TableRow key={technique.id} data-testid="technique-row">
                      <TableCell className="font-medium">
                        <div className="flex items-center space-x-2">
                          <Palette className="w-4 h-4 text-emerald-600" />
                          <span>{technique.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Euro className="w-4 h-4 text-gray-400" />
                          <span className="font-medium">{technique.cost_per_unit.toFixed(2)}</span>
                        </div>
                      </TableCell>
                      <TableCell className="max-w-xs">
                        <div className="truncate" title={technique.description}>
                          {technique.description || 'Sin descripción'}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-gray-600">
                        {new Date(technique.created_at).toLocaleDateString('es-ES')}
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

export default MarkingTechniques;