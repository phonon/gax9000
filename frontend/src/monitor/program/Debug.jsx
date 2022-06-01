/**
 * Render debug data result.
 */

import Plot from "react-plotly.js";
import { colormap, colorTo255Range, colorBrighten } from "../util.js";


export const ProgramDebug = ({
    metadata,
    data,
}) => {
    console.log("RENDERING ProgramDebug");
    console.log(metadata);
    console.log(data);

    const metadataString = JSON.stringify(metadata, null, 2);

    // get num points/bias points
    const numBias = data.v_gs.length
    const numSweeps = data.v_gs[0].length
    const numPoints = data.v_gs[0][0].length

    console.log(`numBias=${numBias}, numSweeps=${numSweeps}, numPoints=${numPoints}`);

    const tracesIdVgs = []
    const tracesIgVgs = []

    for ( let b = 0; b < numBias; b++ ) {
        // base color based on vds bias
        const colBase = colorTo255Range(colormap(b, 0, numBias-1));

        for ( let s = 0; s < numSweeps; s++ ) {
            // make additional sweeps brighter for visibility
            const col = colorBrighten(colBase, 0.5 + (s * 0.5));

            const vds = data.v_ds[b][s][0];
            const vgs = data.v_gs[b][s];
            const id = data.i_d[b][s];
            const ig = data.i_g[b][s];

            tracesIdVgs.push({
                name: `Vds=${vds}, Dir=${s}`,
                x: vgs,
                y: id,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
            });
            
            tracesIgVgs.push({
                name: `Vds=${vds}, Dir=${s}`,
                x: vgs,
                y: ig,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
            });

        }
    }

    return (
        <div>
            <div>
                {metadataString}
            </div>

            {/* Id-Vgs log */}
            <Plot
                data={tracesIdVgs}
                layout={ {
                    title: "Id-Vgs",
                    width: 600,
                    height: 600,
                    xaxis: {
                        type: "linear",
                        autorange: true,
                    },
                    yaxis: {
                        type: "log",
                        autorange: true,
                    }
                } }
            />

            {/* Id-Vgs linear */}
            <Plot
                data={tracesIdVgs}
                layout={ {
                    title: "Id-Vgs",
                    width: 600,
                    height: 600,
                    xaxis: {
                        type: "linear",
                        autorange: true,
                    },
                    yaxis: {
                        type: "linear",
                        autorange: true,
                    }
                } }
            />

            {/* Ig-Vgs log */}
            <Plot
                data={tracesIgVgs}
                layout={ {
                    title: "Ig-Vgs",
                    width: 600,
                    height: 600,
                    xaxis: {
                        type: "linear",
                        autorange: true,
                    },
                    yaxis: {
                        type: "log",
                        autorange: true,
                    }
                } }
            />
        </div>
    );
}
