/**
 * Render Id-Vgs data result.
 */

 import {
    Accordion, AccordionSummary, AccordionDetails,
    Box,
    Table, TableContainer, TableHead, TableRow, TableCell, TableBody,
    Typography,
} from "@mui/material";
import Plot from "react-plotly.js";
import { colormap, colorTo255Range, colorBrighten } from "../util.js";


export const ProgramIdVgs = ({
    metadata,
    data,
}) => {
    console.log("RENDERING ProgramIdVgs");
    console.log(metadata);
    console.log(data);

    const metadataString = JSON.stringify(metadata, null, 2);

    // get num points/bias points from data shape: (bias, sweeps, points)
    const numBias = data.v_gs.length;
    const numSweeps = data.v_gs[0].length;
    const numPoints = data.v_gs[0][0].length;

    console.log(`numBias=${numBias}, numSweeps=${numSweeps}, numPoints=${numPoints}`);

    const tracesIdVgs = [];
    const tracesIgVgs = [];

    // key properties to display in data table
    const vdsList = [];
    const idMaxList = [];
    const idMinList = [];
    const onOffList = [];
    const igMaxList = [];

    for ( let b = 0; b < numBias; b++ ) {
        // base color based on vds bias (note, color [vmin, vmax] range expanded to make colors nicer)
        const colBase = colorTo255Range(colormap(b, -1, numBias));
        
        // add vds bias
        vdsList.push(data.v_ds[b][0][0]);

        for ( let s = 0; s < numSweeps; s++ ) {
            // make additional sweeps brighter for visibility
            const col = colorBrighten(colBase, 0.6 + (s * 0.4));

            const vds = data.v_ds[b][s][0];
            const vgs = data.v_gs[b][s];
            const id = data.i_d[b][s];
            const ig = data.i_g[b][s];
            
            // key performance metrics (only do for first sweep):
            // find max/min id and max ig in range
            if ( s === 0 ) {
                const idMax = Math.max(...id);
                const idMin = Math.min(...id);
                const igMax = Math.max(...ig);
                const onOff = idMax / idMin;
                idMaxList.push(idMax.toExponential(2));
                idMinList.push(idMin.toExponential(2));
                onOffList.push(onOff.toExponential(2));
                igMaxList.push(igMax.toExponential(2));
            }

            // create plot traces
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

    const tableRows = [
        { name: "Id Max", values: idMaxList },
        { name: "Id Min", values: idMinList },
        { name: "On/Off", values: onOffList },
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
                                <TableCell>Vds</TableCell>
                                {vdsList.map((vds, i) =>
                                    <TableCell key={i}>{vds}</TableCell>
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
                                {metadataString}
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
                {/* Id-Vgs log */}
                <Plot
                    data={tracesIdVgs}
                    layout={ {
                        title: "Id-Vgs (Log Scale)",
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
                        title: "Id-Vgs (Linear Scale)",
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
            </Box>
            
        </Box>
    );
}
