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


export const ProgramRram1T1R = ({
    metadata,
    data,
}) => {
    console.log("RENDERING ProgramRram1T1R");
    console.log(metadata);
    console.log(data);

    const measurementConfigString = JSON.stringify(metadata.config, null, 2);

    // Rram measurement data format contains padded arrays:
    // v_d sequences = 
    //      FORM  [0,   1,   2,   3,   4]
    //      RESET [0,  -1,  -2,  -3, nan]
    //      SET   [0,   1,   2, nan, nan]
    //      RESET [0,  -1,  -2,  -3, nan]
    //      SET   [0,   1,   2, nan, nan]
    //      RESET [0,  -1,  -2,  -3, nan]
    // 
    // Overall rram data block shape is:
    //      (num_sequences, num_directions, num_points_max)
    // for run-time updates, `num_sequences = metadata.step` which is number of
    // steps that have completed. 
    const numSequences = metadata.step !== undefined ? metadata.step : data.v_d.length;
    const numDirections = data.v_d[0].length;
    const numPointsMax = data.v_d[0][0].length;

    // this gives step name and num points for each sequence,
    // e.g. numPoints[0] = number of points for measurement sequence 1
    const sequenceNumPoints = data.num_points;
    const sequenceStepNames = data.step_names;

    console.log(`numSequences=${numSequences}, numDirections=${numDirections}, numPointsMax=${numPointsMax}`);

    // plot traces
    const tracesIdVd = [];  // id vs vd
    const tracesResVd = []; // res vs vd, res = vd/id
    const tracesIgVd = [];  // ig vs vd

    // key properties to display in data table
    const resList = [];   // resistance = abs(v_d / i_d) at end point of each sequence step
    const idMaxList = [];
    const idMinList = [];
    const igMaxList = [];

    for ( let s = 0; s < numSequences; s++ ) {
        // number of points for this sequence
        const n = sequenceNumPoints[s];

        // base color based on vds bias (note, color [vmin, vmax] range expanded to make colors nicer)
        const colBase = colorTo255Range(colormap(s, -1, numSequences));

        for ( let d = 0; d < numDirections; d++ ) {
            // make additional sweeps brighter for visibility
            const col = colorBrighten(colBase, 0.6 + (d * 0.4));

            // unpack data
            const vs = data.v_s[s][d][0]; // const
            const vd = data.v_d[s][d].slice(0, n);
            const vg = data.v_g[s][d].slice(0, n);
            const id = data.i_d_abs[s][d].slice(0, n);
            const ig = data.i_g_abs[s][d].slice(0, n);
            const res = data.res[s][d].slice(0, n);

            // key performance metrics (only do for first sweep):
            // find max/min id and max ig in range
            if ( d === 0 ) {
                const idMax = Math.max(...id);
                const idMin = Math.min(...id);
                const igMax = Math.max(...ig);
                resList.push(res[n-1].toExponential(2));
                idMaxList.push(idMax.toExponential(2));
                idMinList.push(idMin.toExponential(2));
                igMaxList.push(igMax.toExponential(2));
            }

            // create plot traces
            tracesIdVd.push({
                name: `${sequenceStepNames[s]}, dir=${d}`,
                x: vd,
                y: id,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
            });

            tracesResVd.push({
                name: `${sequenceStepNames[s]}, dir=${d}`,
                x: vd,
                y: res,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
            });
            
            tracesIgVd.push({
                name: `${sequenceStepNames[s]}, dir=${d}`,
                x: vd,
                y: ig,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
            });
        }
    }

    const tableRows = [
        { name: "Res", values: resList },
        { name: "Id Max", values: idMaxList },
        { name: "Id Min", values: idMinList },
        { name: "Ig Max", values: igMaxList },
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
                                <TableCell>Step</TableCell>
                                {sequenceStepNames.map((step, i) =>
                                    <TableCell key={i}>{step}</TableCell>
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
                {/* Id-Vd log */}
                <Plot
                    data={tracesIdVd}
                    layout={ {
                        title: "Id-Vd (Log Scale)",
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

                {/* Res-Vd log */}
                <Plot
                    data={tracesResVd}
                    layout={ {
                        title: "R-Vd (Log Scale)",
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

                {/* Ig-Vd log */}
                <Plot
                    data={tracesIgVd}
                    layout={ {
                        title: "Ig-Vd (Log Scale)",
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
