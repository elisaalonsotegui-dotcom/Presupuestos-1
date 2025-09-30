import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Package, FileText, History, Plus, TrendingUp } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Dashboard = ({ user }) => {
  const [stats, setStats] = useState({
    products: 0,
    quotes: 0,
    markingTechniques: 0
  });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const [productsRes, quotesRes, markingRes] = await Promise.all([
        axios.get(`${API}/products`, { headers }),
        axios.get(`${API}/quotes`, { headers }),
        axios.get(`${API}/marking-techniques`, { headers })
      ]);
      
      setStats({
        products: productsRes.data.length,
        quotes: quotesRes.data.length,
        markingTechniques: markingRes.data.length
      });
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const dashboardCards = [
    {
      title: 'Productos',
      count: stats.products,
      icon: Package,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      link: '/products',
      action: 'Gestionar productos'
    },
    {
      title: 'Presupuestos',
      count: stats.quotes,
      icon: FileText,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-50',
      link: '/quotes',
      action: 'Crear presupuesto'
    },
    {
      title: 'Historial',
      count: stats.quotes,
      icon: History,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
      link: '/history',
      action: 'Ver historial'
    }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          ¡Bienvenido, {user.username}!
        </h1>
        <p className="text-gray-600">
          Gestiona tus productos y crea presupuestos profesionales de manera eficiente.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {dashboardCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <Card key={index} className="hover:shadow-lg transition-shadow duration-300 border-0 bg-white/90 backdrop-blur-sm">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className={`p-3 rounded-lg ${card.bgColor}`}>
                    <Icon className={`w-6 h-6 ${card.color}`} />
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">{card.count}</p>
                    <p className="text-sm text-gray-600">{card.title}</p>
                  </div>
                </div>
                <Link to={card.link}>
                  <Button className="w-full bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200">
                    {card.action}
                  </Button>
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Plus className="w-5 h-5 text-emerald-600" />
              <span>Acciones Rápidas</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link to="/products" className="block">
              <Button variant="outline" className="w-full justify-start" data-testid="quick-upload-products">
                <Package className="w-4 h-4 mr-2" />
                Subir productos desde Excel
              </Button>
            </Link>
            <Link to="/quotes" className="block">
              <Button variant="outline" className="w-full justify-start" data-testid="quick-generate-quote">
                <FileText className="w-4 h-4 mr-2" />
                Generar nuevo presupuesto
              </Button>
            </Link>
            <Link to="/marking" className="block">
              <Button variant="outline" className="w-full justify-start" data-testid="quick-manage-marking">
                <TrendingUp className="w-4 h-4 mr-2" />
                Gestionar técnicas de marcaje
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card className="border-0 bg-white/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>Resumen del Sistema</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-emerald-50 rounded-lg">
              <span className="text-emerald-700 font-medium">Total de productos</span>
              <span className="text-emerald-900 font-bold">{stats.products}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
              <span className="text-blue-700 font-medium">Presupuestos creados</span>
              <span className="text-blue-900 font-bold">{stats.quotes}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-purple-50 rounded-lg">
              <span className="text-purple-700 font-medium">Técnicas de marcaje</span>
              <span className="text-purple-900 font-bold">{stats.markingTechniques}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;