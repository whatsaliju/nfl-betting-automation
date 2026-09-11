import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./personal.css";
import PersonalApp from "./PersonalApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PersonalApp />
  </StrictMode>
);
