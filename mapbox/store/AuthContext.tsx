import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AuthUser } from '../types';

interface AuthContextState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (user: AuthUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextState | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // Rehydrate session from local storage on mount
    const storedToken = localStorage.getItem('admin_token');
    const storedRole = localStorage.getItem('admin_role');
    
    if (storedToken && storedRole) {
      setUser({
        token: storedToken,
        role: storedRole as AuthUser['role'],
        permission_keys: [], // In a real app, fetch fresh permissions on reload
      });
    }
    setIsInitialized(true);
  }, []);

  const login = (newUser: AuthUser) => {
    localStorage.setItem('admin_token', newUser.token);
    localStorage.setItem('admin_role', newUser.role);
    setUser(newUser);
  };

  const logout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_role');
    setUser(null);
  };

  if (!isInitialized) {
    return null; // Or a loading spinner
  }

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
