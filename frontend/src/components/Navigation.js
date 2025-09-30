import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from './ui/button';
import { Calculator, LogOut, Home, Package, FileText, History, Settings } from 'lucide-react';

const Navigation = ({ user, onLogout }) => {
  const location = useLocation();

  const navItems = [
    { path: '/dashboard', label: 'Inicio', icon: Home },
    { path: '/products', label: 'Productos', icon: Package },
    { path: '/quotes', label: 'Presupuestos', icon: FileText },
    { path: '/history', label: 'Historial', icon: History },
    { path: '/marking', label: 'Marcajes', icon: Settings },
  ];

  return (
    <nav className="bg-white/90 backdrop-blur-sm border-b shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/dashboard" className="flex items-center space-x-2">
              <Calculator className="w-8 h-8 text-emerald-600" />
              <span className="text-xl font-bold text-gray-800">Presupuestos Pro</span>
            </Link>
            
            <div className="hidden md:flex space-x-4">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive 
                        ? 'bg-emerald-100 text-emerald-700' 
                        : 'text-gray-600 hover:text-emerald-600 hover:bg-emerald-50'
                    }`}
                    data-testid={`nav-${item.label.toLowerCase()}`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600">
              Hola, <span className="font-medium">{user.username}</span>
            </span>
            <Button
              onClick={onLogout}
              variant="outline"
              size="sm"
              className="text-gray-600 hover:text-red-600 hover:border-red-300"
              data-testid="logout-button"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Salir
            </Button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;