/**
 * Render unknown program. Just show program config.
 */

 import {
    Accordion, AccordionSummary, AccordionDetails,
    Box,
    Table, TableContainer, TableHead, TableRow, TableCell, TableBody,
    Typography,
} from "@mui/material";


export const ProgramUnknown = ({
    name,
    metadata,
}) => {
    const metadataString = JSON.stringify(metadata, null, 2);

    return (
        <>
        <Typography variant="h6">Unknown Program: {name}</Typography>
        <Typography component="div" variant="body1">
            <pre style={{overflow: "scroll"}}>
                {metadataString}
            </pre>
        </Typography>
        </>
    );
}
