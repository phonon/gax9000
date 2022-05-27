import {
    Box,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    FormControl,
    Grid,
    InputLabel,
    MenuItem,
    Select,
    TextField,
    Table, TableContainer, TableHead, TableRow, TableCell, TableBody,
    Typography,
} from "@mui/material";


export const DialogRunMeasurement = ({
    open,
    handleClose,
    runMeasurement,
    currentDieX,
    currentDieY,
    deviceX,
    deviceY,
    deviceRow,
    deviceCol,
    dataFolder,
    program,
    programConfig,
    sweep,
    sweepConfig,
    sweepSaveData,
}) => {
    function createRowData(name, value) {
        return { name, value };
    }
    
    const rows = [
        createRowData("Die X", currentDieX),
        createRowData("Die Y", currentDieY),
        createRowData("Device Row", deviceRow),
        createRowData("Device Col", deviceCol),
        createRowData("Device X", deviceX),
        createRowData("Device Y", deviceY),
        createRowData("Data Folder", dataFolder),
        createRowData("Save Data", String(sweepSaveData)),
    ];

    return (
        <Dialog
            open={open}
            onClose={handleClose}
            scroll="body"
            fullWidth
            maxWidth="xs"
        >
            <DialogTitle>Run Measurement Sweep</DialogTitle>
            <DialogContent>
                <DialogContentText>
                    Confirm measurement sweep parameters:
                </DialogContentText>

                <TableContainer >
                    <Table aria-label="simple table">
                        <TableBody>
                        {rows.map((row) => (
                            <TableRow
                                key={row.name}
                                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                            >
                                <TableCell component="th" scope="row">{row.name}</TableCell>
                                <TableCell align="right">{row.value}</TableCell>
                            </TableRow>
                        ))}
                        </TableBody>
                    </Table>
                </TableContainer>
                
                <Box height="20px"/>

                <Typography component="div" variant="body1">
                    <Box
                        sx={{}}
                    >
                        <b>Program:</b> {program}
                    </Box>
                    <Box
                        sx={{ border: "1px solid rgba(0, 0, 0, 0.3)", padding: "0px 16px"}}
                    >
                        <pre>
                            {programConfig}
                        </pre>
                    </Box>
                    
                    <Box height="40px"/>

                    <Box
                        sx={{}}
                    >
                        <b>Sweep:</b> {sweep}
                    </Box>
                    <Box
                        sx={{ border: "1px solid rgba(0, 0, 0, 0.3)", padding: "0px 16px"}}
                    >
                        <pre>
                            {sweepConfig}
                        </pre>
                    </Box>
                </Typography>
                
            </DialogContent>
            <DialogActions>
                <Button variant="contained" onClick={runMeasurement}>Confirm</Button>
                <Button variant="outlined" color="error" onClick={handleClose}>Cancel</Button>
            </DialogActions>
        </Dialog>
    );
};