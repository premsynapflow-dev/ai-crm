import React, { createContext, useContext, useState } from "react";
import { User } from "./api";

// -- Storage helpers ---------------------------------------------------------
// "Remember me" = localStorage (survives browser close)
// No remember me  = sessionStorage (survives refresh, cleared on browser close)

function readToken(): string | null {
  return localStorage.getItem("synapflow_token") || sessionStorage.getItem("synapflow_token");
}

function readUser(): User | null {
  try {
    const raw = localStorage.getItem("synapflow_user") || sessionStorage.getItem("synapflow_user");
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function writeSession(token: string, user: User, apiKey: string | undefined, remember: boolean) {
  const store = remember ? localStorage : sessionStorage;
  const other = remember ? sessionStorage : localStorage;
  store.setItem("synapflow_token", token);
  store.setItem("synapflow_user", JSON.stringify(user));
  if (apiKey) store.setItem("synapflow_api_key", apiKey);
  // Clear from the other storage to avoid stale reads
  other.removeItem("synapflow_token");
  other.removeItem("synapflow_user");
  other.removeItem("synapflow_api_key");
}

function clearSession() {
  ["synapflow_token", "synapflow_user", "synapflow_api_key"].forEach((k) => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
}

// ---------------------------------------------------------------------------

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  signup: (data: { name: string; email: string; password: string; businessType: string; phone?: string }) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(readToken);
  const [user, setUser] = useState<User | null>(() => {
    const u = readUser();
    if (!u && readToken()) clearSession(); // corrupted state
    return u;
  });

  const login = async (email: string, password: string, rememberMe = true) => {
    const { api } = await import("./api");
    const response = await api.auth.login(email, password);
    setToken(response.token);
    setUser(response.user);
    writeSession(response.token, response.user, response.user?.apiKey, rememberMe);
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
    // Signup always remembers (user just created the account)
    writeSession(response.token, response.user, response.user?.apiKey, true);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    clearSession();
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
