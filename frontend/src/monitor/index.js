import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ProgramDebug, ProgramIdVds, ProgramIdVgs, ProgramUnknown } from "./program.js";


const Monitor = () => {
    let [render, setRender] = useState((<>Waiting for result..</>))
    
    // route program name => render program jsx
    const renderPrograms = new Map();
    renderPrograms.set("debug", ProgramDebug);
    renderPrograms.set("debug_multistep", ProgramDebug);
    renderPrograms.set("keysight_id_vds", ProgramIdVds);
    renderPrograms.set("keysight_id_vgs", ProgramIdVgs);

    useEffect(() => {
        var eventSrc = new EventSource("https://localhost:9000/subscribe");
        eventSrc.onmessage = (e) => {
            const data = JSON.parse(e.data);
            console.log("EVENT DATA:", data);

            // route program to
            try {
                const program = renderPrograms.get(data.metadata.program);
                if ( program !== undefined ) {
                    setRender(program({ metadata: data.metadata, data: data.data }));
                } else {
                    setRender((<ProgramUnknown name={data.metadata.program} metadata={data.metadata}/>));
                }
            } catch ( err ) {
                console.error(err);
            }
        };

        eventSrc.onerror = (e) => {
            console.error(e);
            eventSrc.close();
        };

        // clean up event channel
        return () => {
            eventSrc.close();
        };
    }, []);

    return (
        <div>
            {render}
        </div>
    )
}

const container = document.getElementById("root");
const root = createRoot(container);
root.render(
    <React.StrictMode>
        <Monitor/>
    </React.StrictMode>
);