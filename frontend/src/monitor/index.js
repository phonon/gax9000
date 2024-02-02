import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ProgramDebug, ProgramIdVds, ProgramIdVgs, ProgramCMOSVoutVin, ProgramRram1T1R, ProgramUnknown } from "./program.js";

// route program name => render program jsx
const renderPrograms = new Map();
renderPrograms.set("debug", ProgramDebug);
renderPrograms.set("debug_multistep", ProgramDebug);
renderPrograms.set("keysight_id_vds", ProgramIdVds);
renderPrograms.set("keysight_id_vds_pulsed_dc", ProgramIdVds);
renderPrograms.set("keysight_id_vgs", ProgramIdVgs);
renderPrograms.set("keysight_id_vgs_pulsed_dc", ProgramIdVgs);
renderPrograms.set("keysight_cmos_vout_vin", ProgramCMOSVoutVin);
renderPrograms.set("keysight_rram_1t1r", ProgramRram1T1R);
renderPrograms.set("keysight_rram_1t1r_sweep", ProgramRram1T1R);
renderPrograms.set("keysight_rram_1t1r_sequence", ProgramRram1T1R);


const Monitor = () => {
    let [render, setRender] = useState((<>Waiting for result..</>));
    let [datasets, setDatasets] = useState(new Map());
    let [append, setAppend] = useState(false); // append = whether to keep same plot data and plot new incoming data
    let [currProgramType, setCurrProgramType] = useState("");

    // When we get data from running the same program type, we may want
    // to append new measurement data to the existing plots.
    // "append" setting = true will force this to happen.
    // However we also have incremental updates from the same dataset
    // (e.g. bias VDS1, VDS2, ... will send multiple of the same).
    // Solution is to map each dataset by its identifying timestamp.
    // So our datasets look like this:
    //      datasets = Map(
    //         timestamp1 => data1,
    //         timestamp2 => data2,
    //         ...  
    //      )
    // If we want to append, when we get incoming data, duplicate our
    // datasets map then replace the corresponding dataset keyed by its
    // timestamp.
    console.log("RECREATING MONITOR, currProgramType = ", currProgramType);

    useEffect(() => {
        console.log("[useEffect] RE-CREATING EVENT SRC");
        var eventSrc = new EventSource("https://localhost:9000/subscribe");
        eventSrc.onmessage = (e) => {
            console.log("currProgramType =", currProgramType);
            console.log("datasets =", datasets);
            const data = JSON.parse(e.data);
            const timestamp = data.metadata.config.timestamp;
            console.log("EVENT DATA:", timestamp, data);

            // route program to
            try {
                const program = renderPrograms.get(data.metadata.program);
                if ( program !== undefined ) {
                    console.log("currProgramType:", currProgramType);
                    let newDatasets;
                    if ( program.name === currProgramType ) {
                        if ( append ) {
                            console.log("APPENDING DATA!!!!!!!");
                            newDatasets = new Map(datasets);
                        } else {
                            newDatasets = new Map();
                        }
                    } else {
                        newDatasets = new Map();
                        console.log("SETTING CURR PROGRAM NAME", program.name);
                        setCurrProgramType(program.name);
                    }

                    newDatasets.set(timestamp, {
                        metadata: data.metadata,
                        data: data.data,
                    });
                    setDatasets(newDatasets);

                    console.log("datasets", newDatasets);

                    setRender(program({ metadata: data.metadata, datasets: newDatasets }));
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
    }, [append, currProgramType, datasets]);

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