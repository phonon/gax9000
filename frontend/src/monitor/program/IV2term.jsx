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


export const ProgramIV2Term = ({
    metadata,
    datasets,
}) => {
    console.log("RENDERING ProgramIV2Term");
    console.log(metadata);
    console.log(datasets);

    const measurementConfigString = JSON.stringify(metadata.config, null, 2);

    // plot traces
    const tracesItV = [];    // it vs vsweep
    const tracesItVlog = []; // it vs vsweep (log)
    const tracesIbV = [];    // ib vs vsweep
    const tracesIbVlog = []; // ib vs vsweep (log)

    // key properties to display in data table
    // TODO: idk?

    for ( const dataset of datasets.values() ) {
        const datasetMetadata = dataset.metadata;
        const data = dataset.data;

        // Measurement data format may padded arrays:
        // v_t sequences = 
        //      fwd1 [0,   1,   2,    3,   4]
        //      fwd2 [0,   1,   2,  nan, nan]
        //      neg1 [0,  -1,  -2,   -3,  -4]
        //      neg2 [0,  -1,  -2,  nan, nan]
        //      ...
        // 
        // Overall v_t and i_t data block shape is:
        //      (num_sweeps, num_points_max)
        // for run-time updates, `num_sweeps = datasetMetadata.step` which is number of
        // steps that have completed. 
        const numSweeps = datasetMetadata.step !== undefined ? datasetMetadata.step : data.v_t.length;
        const numPointsMax = data.v_t[0].length;

        // this gives step name and num points for each sequence,
        // e.g. numPoints[0] = number of points for measurement sequence 1
        const sweepNumPoints = data.points;

        console.log(`numSweeps=${numSweeps}, numPointsMax=${numPointsMax}`);

        for ( let s = 0; s < numSweeps; s++ ) {
            // number of points for this sequence
            const n = sweepNumPoints[s];

            // base color based on vds bias (note, color [vmin, vmax] range expanded to make colors nicer)
            const color = colorTo255Range(colormap(s, -1, numSweeps));

            // unpack data
            const vt = data.v_t[s].slice(0, n);
            const vb = data.v_b[s].slice(0, n);
            const it = data.i_t[s].slice(0, n);
            const ib = data.i_b[s].slice(0, n);
            const itAbs = it.map(Math.abs);
            const ibAbs = ib.map(Math.abs);

            // determine which one was the sweep voltage
            const vsweep = vt[0] == vt[1] ? vb : vt;

            // create plot traces
            tracesItV.push({
                name: `sweep ${s}`,
                x: vsweep,
                y: it,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${color[0]},${color[1]},${color[2]})`},
            });
            tracesItVlog.push({
                name: `sweep ${s}`,
                x: vsweep,
                y: itAbs,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${color[0]},${color[1]},${color[2]})`},
            });
            tracesIbV.push({
                name: `sweep ${s}`,
                x: vsweep,
                y: ib,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${color[0]},${color[1]},${color[2]})`},
            });
            tracesIbVlog.push({
                name: `sweep ${s}`,
                x: vsweep,
                y: ibAbs,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${color[0]},${color[1]},${color[2]})`},
            });
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
                {/* It-V linear */}
                <Plot
                    data={tracesItV}
                    layout={ {
                        title: "It-V (Linear)",
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

                {/* It-V log */}
                <Plot
                    data={tracesItVlog}
                    layout={ {
                        title: "|It|-V (Log)",
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

                {/* Ib-V linear */}
                <Plot
                    data={tracesIbV}
                    layout={ {
                        title: "Ib-V (Linear)",
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

                {/* Ib-V log */}
                <Plot
                    data={tracesIbVlog}
                    layout={ {
                        title: "|Ib|-V (Log)",
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
