import { createContext, useContext, useState } from "react";
import { ROLES } from "../config";

const RoleContext = createContext(null);

export function RoleProvider({ children }) {
  // In a real app this comes from auth. For now, toggle manually.
  const [role, setRole] = useState(ROLES.MANAGER);

  return (
    <RoleContext.Provider value={{ role, setRole, ROLES }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  return useContext(RoleContext);
}