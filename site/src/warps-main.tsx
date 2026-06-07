import React from "react";
import ReactDOM from "react-dom/client";
import WARPSApp from "./WARPSApp";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("warps-root")!).render(
  <React.StrictMode>
    <WARPSApp />
  </React.StrictMode>
);
