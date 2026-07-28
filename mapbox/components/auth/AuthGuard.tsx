import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../store/AuthContext';

export const AuthGuard: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    // Redirect to login while saving the attempted url
    return <Navigate to="/admin/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
};
