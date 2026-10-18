import { createContext } from "react";

// Value is provided by WorkspaceProvider; read it through useWorkspace().
export const WorkspaceContext = createContext(null);
