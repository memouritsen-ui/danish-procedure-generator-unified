import { PropsWithChildren } from "react";
import { NavLink } from "react-router-dom";

export default function Layout({ children }: PropsWithChildren) {
  return (
    <>
      <nav className="nav">
        <NavLink to="/write" className={({ isActive }) => (isActive ? "active" : "")}>
          Skriv procedure
        </NavLink>
        <NavLink to="/runs" className={({ isActive }) => (isActive ? "active" : "")}>
          Runs
        </NavLink>
        <NavLink to="/sources" className={({ isActive }) => (isActive ? "active" : "")}>
          Kilder
        </NavLink>
        <NavLink to="/versions" className={({ isActive }) => (isActive ? "active" : "")}>
          Versioner
        </NavLink>
        <NavLink to="/templates" className={({ isActive }) => (isActive ? "active" : "")}>
          Skabeloner
        </NavLink>
        <NavLink to="/protocols" className={({ isActive }) => (isActive ? "active" : "")}>
          Protokoller
        </NavLink>
        <NavLink to="/ingest" className={({ isActive }) => (isActive ? "active" : "")}>
          Ingest
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
          Indstillinger
        </NavLink>
      </nav>
      <div className="container">{children}</div>
    </>
  );
}
