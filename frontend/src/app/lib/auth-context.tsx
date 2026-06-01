import React, { createContext, useContext, useState, useEffect } from "react";
import { User } from "./api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (data: { name: string; email: string; password: string; businessType: string; phone?: string }) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const storedToken = localStorage.getItem("synapflow_token");
    const storedUser = localStorage.getItem("synapflow_user");
    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem("synapflow_token");
        localStorage.removeItem("synapflow_user");
        localStorage.removeItem("synapflow_api_key");
      }
    }
  }, []);

  const login = async (email: string, password: string) => {
    const { api } = await import("./api");
    const response = await api.auth.login(email, password);
    setToken(response.token);
    setUser(response.user);
    localStorage.setItem("synapflow_token", response.token);
    localStorage.setItem("synapflow_user", JSON.stringify(response.user));
  };

  const signup = async (data: {
    name: string;
    email: string;
    password: string;
    businessType: string;
    phone?: string;
  }) => {
    const { api } = await import("./api");
    const response = await api.auth.signup(data);
    setToken(response.token);
    setUser(response.user);
    localStorage.setItem("synapflow_token", response.token);
    localStorage.setItem("synapflow_user", JSON.stringify(response.user));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("synapflow_token");
    localStorage.removeItem("synapflow_user");
    localStorage.removeItem("synapflow_api_key");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        signup,
        logout,
        isAuthenticated: !!token,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
