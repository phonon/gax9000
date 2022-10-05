import React from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import App from "./App";

const api = axios.create({
    // baseURL: process.env.REACT_APP_BASE_URL || "https://localhost:9000",
    baseURL: "https://localhost:9000",
});

const container = document.getElementById("root");
const root = createRoot(container);
root.render(
    <React.StrictMode>
        <App
            axios={api}
        />
    </React.StrictMode>
);