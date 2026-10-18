import { createContext } from "react";

// Value is provided by AuthProvider; read it through useAuth().
export const AuthContext = createContext(null);
