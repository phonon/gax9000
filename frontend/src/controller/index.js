import React from "react";
import ReactDOM from "react-dom";
import axios from "axios";
import App from "./App";

const api = axios.create({
    // baseURL: process.env.REACT_APP_BASE_URL || "https://localhost:9000",
    baseURL: "https://localhost:9000",
});

ReactDOM.render(
    <React.StrictMode>
        <App
            axios={api}
        />
    </React.StrictMode>,
    document.getElementById("root"),
);
