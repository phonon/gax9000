/**
 * Renderers for RRAM, 1T1R, etc. device measurements
 */

import {
    Accordion, AccordionSummary, AccordionDetails,
    Box,
    Table, TableContainer, TableHead, TableRow, TableCell, TableBody,
    Typography,
} from "@mui/material";
import Plot from "react-plotly.js";
import { colormap, colorTo255Range, colorBrighten } from "../util.js";


export const ProgramCMOSVoutVin = ({
    metadata,
    datasets,
}) => {
    console.log("RENDERING ProgramCMOSVoutVin");
    console.log(metadata);
    console.log(datasets);

    const measurementConfigString = JSON.stringify(metadata.config, null, 2);

    // plot traces
    const tracesVoutVin = []; // vout vs vin sweep (main)
    const tracesIddVin = [];  // idd vs vin sweep (to see transient)
    const tracesIgVin = [];  // input gate currents vs Vin sweep

    // key properties to display in data table
    const vConstList = []; // non-input vconst values in each sweep

    let sequenceStepNames = undefined; 

    for ( const dataset of datasets.values() ) {
        const datasetMetadata = dataset.metadata;
        const data = dataset.data;

        // Overall data block shape is:
        //      (numConstInputs, numDirections, numPoints)
        // for run-time updates, `numConstInputs = datasetMetadata.step` which is number of
        // steps that have completed.
        // numConstInputs = number of non-swept input values (e.g. 0, 1.2)
        // numDirections = number of forward/reverse sweeps for swept input
        // numPoints = number of points in input sweep 
        const numInputs = data.inputs;
        const numConstInputs = datasetMetadata.step !== undefined ? datasetMetadata.step : data.v_out.length;
        const numDirections = data.v_out[0].length;
        const numPoints = data.v_out[0][0].length;
        const inSweep = data.in_sweep; // name of input swept, "v_a" or "v_b"
        const inConst = data.in_const; // name of input constant, "v_b" or "v_a"

        console.log(`numConstInputs=${numConstInputs}, numDirections=${numDirections}, numPoints=${numPoints}`);

        for ( let i = 0; i < numConstInputs; i++ ) {

            // base color based on vds bias (note, color [vmin, vmax] range expanded to make colors nicer)
            const colBase = colorTo255Range(colormap(i, -1, numConstInputs));

            for ( let d = 0; d < numDirections; d++ ) {
                // make additional sweeps brighter for visibility
                const col = colorBrighten(colBase, 0.6 + (d * 0.4));

                // unpack data
                const va = data.v_a[i][d];
                const ia = data.i_a[i][d];
                const vb = "v_b" in data ? data.v_b[i][d] : [0];
                const ib = "i_b" in data ? data.i_b[i][d] : [0];
                const vout = data.v_out[i][d];
                const idd = data.i_dd[i][d];

                // determine vin being swept and other input being constant
                const vin = ( inSweep === "v_a" ) ? va : vb;
                const vconst = ( inSweep === "v_a" ) ? vb[i] : va[i];

                vConstList.push(vconst);

                // create plot traces
                tracesVoutVin.push({
                    name: `vout (v2 = ${vconst}, dir=${d})`,
                    x: vin,
                    y: vout,
                    type: "scatter",
                    mode: "lines+markers",
                    marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
                });

                // supply current
                tracesIddVin.push({
                    name: `idd, (v2 = ${vconst}, dir=${d})`,
                    x: vin,
                    y: idd,
                    type: "scatter",
                    mode: "lines+markers",
                    marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
                });
                
                // input gate currents
                tracesIgVin.push({
                    name: `ia, (v2 = ${vconst}, dir=${d})`,
                    x: vin,
                    y: ia,
                    type: "scatter",
                    mode: "lines+markers",
                    marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
                });
                if ( numInputs == 2 ) {
                    tracesIgVin.push({
                        name: `ib, (v2 = ${vconst}, dir=${d})`,
                        x: vin,
                        y: ib,
                        type: "scatter",
                        mode: "lines+markers",
                        marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
                    });
                }
            }
        }
    }

    const tableRows = [

    ]

    return (
        <Box sx={{
            display: "flex",
            flexDirection: "row",
            flexWrap: "wrap",
            height: "95vh",
            width: "95vw",
        }}>
            <Box sx={{
                flexGrow: 0,
                flexShrink: 0,
                width: "20%",
                minWidth: "200px",
                maxWidth: "400px",
            }}>
                {/* Key results table */}
                <Typography variant="h6">Metrics</Typography>
                <TableContainer>
                    <Table size="small" aria-label="metrics table">
                        <TableHead>
                            <TableRow>
                                <TableCell>V Other</TableCell>
                                {vConstList.map((v, i) =>
                                    <TableCell key={i}>{v}</TableCell>
                                )}
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {tableRows.map((row, r) =>
                                <TableRow
                                    key={row.name}
                                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                                >
                                    <TableCell component="th" scope="row">{row.name}</TableCell>
                                    {row.values.map((v, i) =>
                                        <TableCell key={i}>{v}</TableCell>
                                    )}
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>

                {/* Measurement Config */}
                <Accordion>
                    <AccordionSummary
                        expandIcon={"⮟"}
                    >
                        <Typography variant="body1">Measurement Config</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Typography component="div" variant="body1">
                            <pre style={{overflow: "scroll"}}>
                                {measurementConfigString}
                            </pre>
                        </Typography>
                    </AccordionDetails>
                </Accordion>
            </Box>

            {/* PLOTS */}
            <Box sx={{
                flexGrow: 1,
                minWidth: "400px",
                maxWidth: "75%",
                height: "100%",
                overflow: "scroll",
            }}>
                {/* Vout Vin */}
                <Plot
                    data={tracesVoutVin}
                    layout={ {
                        title: "Vout-Vin",
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

                {/* IDD Vin Transient */}
                <Plot
                    data={tracesIddVin}
                    layout={ {
                        title: "IDD-Vin",
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

                {/* Ig-Vin log */}
                <Plot
                    data={tracesIgVin}
                    layout={ {
                        title: "Ig-Vin (Log Scale)",
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
            </Box>
            
        </Box>
    );
}
