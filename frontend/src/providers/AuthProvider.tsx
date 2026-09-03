import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import * as authApi from "@/api/auth";
import { ApiError } from "@/api/client";
import { onSessionExpired } from "@/api/sessionEvents";
import type { User } from "@/types/user";

export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  // On mount: the browser sends the httpOnly session cookie automatically, so this
  // restores the session across page reloads without ever touching the token in JS.
  useEffect(() => {
    authApi
      .fetchCurrentUser()
      .then(setUser)
      .catch((err: unknown) => {
        if (!(err instanceof ApiError && err.status === 401)) {
          console.error("Failed to restore session", err);
        }
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  // The sole subscriber to api/client.ts's session-expired signal (see
  // docs/requirements/auth.md's design doc) — this is the one place `user` gets
  // cleared and the app navigates to /login in response to a session dying
  // mid-use, rather than each screen independently reacting to its own failed
  // request. See sessionEvents.ts for why this is an event bridge rather than a
  // hard window.location redirect.
  useEffect(() => {
    return onSessionExpired(() => {
      setUser(null);
      navigate("/login", { replace: true });
    });
  }, [navigate]);

  const login = useCallback(async (email: string, password: string) => {
    const loggedInUser = await authApi.login({ email, password });
    setUser(loggedInUser);
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
