import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import { ProgramDebug, ProgramIdVds, ProgramIdVgs } from "./program.js";


const Monitor = () => {
    let [render, setRender] = useState((<>Waiting for result..</>))
    
    // route program name => render program jsx
    const renderPrograms = new Map();
    renderPrograms.set("debug", ProgramDebug);
    renderPrograms.set("keysight_id_vds", ProgramIdVds);
    renderPrograms.set("keysight_id_vgs", ProgramIdVgs);

    useEffect(() => {
        var eventSrc = new EventSource("https://localhost:9000/subscribe");
        eventSrc.onmessage = (e) => {
            const data = JSON.parse(e.data);
            console.log(data);

            // route program to
            try {
                console.log(data.metadata.program);
                console.log(data);
                const program = renderPrograms.get(data.metadata.program);
                console.log("program:", program, ProgramDebug);
                if ( program !== undefined ) {
                    setRender(program({ metadata: data.metadata, data: data.data }));
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

ReactDOM.render(
  <React.StrictMode>
    <Monitor/>
  </React.StrictMode>,
  document.getElementById("root")
);
