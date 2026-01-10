import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { httpBatchLink } from '@trpc/client';
import { trpc } from './utils/trpc';
import LandingPage from './pages/LandingPage';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import Configuracoes from './pages/Configuracoes';
import DominiosPage from './pages/configuracoes/dominios';
import ProtectedRoute from './components/ProtectedRoute';
import './App.css';

const queryClient = new QueryClient();

const trpcClient = trpc.createClient({
  links: [
    httpBatchLink({
      url: `${import.meta.env.VITE_API_URL || 'http://localhost:3000'}/trpc`,
      credentials: 'include',
    }),
  ],
});

/**
 * Componente principal da aplicação
 * Integra autenticação, roteamento e contexto global
 * 
 * Funcionalidades:
 * - Autenticação com JWT
 * - Proteção de rotas
 * - Dashboard com agentes de IA
 * - Gerenciamento de domínios
 * - Configurações de workspace
 */
export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Verificar se usuário está autenticado
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        if (token) {
          setIsAuthenticated(true);
        }
      } catch (error) {
        console.error('Erro ao verificar autenticação:', error);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-orange-500 to-purple-600">
        <div className="text-white text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
          <p>Carregando...</p>
        </div>
      </div>
    );
  }

  return (
    <trpc.Provider client={trpcClient} queryClient={queryClient}>
      <QueryClientProvider client={queryClient}>
        <Router>
          <Routes>
            {/* Rotas públicas */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/signup" element={<Signup setIsAuthenticated={setIsAuthenticated} />} />

            {/* Rotas protegidas */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/configuracoes"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <Configuracoes />
                </ProtectedRoute>
              }
            />
            <Route
              path="/configuracoes/dominios"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <DominiosPage />
                </ProtectedRoute>
              }
            />

            {/* Rota padrão */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Router>
      </QueryClientProvider>
    </trpc.Provider>
  );
}
