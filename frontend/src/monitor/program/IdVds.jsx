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


export const ProgramIdVds = ({
    metadata,
    data,
}) => {
    console.log("RENDERING ProgramIdVds");
    console.log(metadata);
    console.log(data);

    const metadataString = JSON.stringify(metadata, null, 2);

    // get num points/bias points from data shape: (bias, sweeps, points)
    const numBias = data.v_ds.length;
    const numSweeps = data.v_ds[0].length;
    const numPoints = data.v_ds[0][0].length;

    console.log(`numBias=${numBias}, numSweeps=${numSweeps}, numPoints=${numPoints}`);

    const tracesIdVds = [];
    const tracesIgVds = [];

    // key properties to display in data table
    const vgsList = [];
    const idMaxList = [];
    const igMaxList = [];

    for ( let b = 0; b < numBias; b++ ) {
        // base color based on vds bias
        const colBase = colorTo255Range(colormap(b, 0, numBias-1));
        
        // add vgs bias
        vgsList.push(data.v_gs[b][0][0]);

        for ( let s = 0; s < numSweeps; s++ ) {
            // make additional sweeps brighter for visibility
            const col = colorBrighten(colBase, 0.5 + (s * 0.5));

            const vgs = data.v_gs[b][s][0];
            const vds = data.v_ds[b][s];
            const id = data.i_d[b][s];
            const ig = data.i_g[b][s];
            
            // key performance metrics (only do for first sweep):
            if ( s === 0 ) {
                const idMax = Math.max(...id);
                const igMax = Math.max(...ig);
                idMaxList.push(idMax.toExponential(2));
                igMaxList.push(igMax.toExponential(2));
            }

            // create plot traces
            tracesIdVds.push({
                name: `Vgs=${vgs}, Dir=${s}`,
                x: vds,
                y: id,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
            });
            
            tracesIgVds.push({
                name: `Vgs=${vgs}, Dir=${s}`,
                x: vds,
                y: ig,
                type: "scatter",
                mode: "lines+markers",
                marker: {color: `rgb(${col[0]},${col[1]},${col[2]})`},
            });
        }
    }

    const tableRows = [
        { name: "Id Max", values: idMaxList },
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
                    <Table component="paper" size="small" aria-label="metrics table">
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
                {/* Id-Vds */}
                <Plot
                    data={tracesIdVds}
                    layout={ {
                        title: "Id-Vds",
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
                    data={tracesIgVds}
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
