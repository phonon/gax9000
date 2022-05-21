import {
    Button, 
    Container,
    Divider,
    FormControl,
    Grid,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    TextField,
} from "@mui/material";

/**
 * Instrument GPIB connection bar
 */
export const InstrumentConnection = (props) => {
    
    return (
        <Grid
            container
            spacing={0}
            direction="row"
        >
            {/* GPIB address identification display */}
            <Grid item xs={7}>
                <TextField
                    fullWidth
                    id="outlined-basic"
                    label={props.label}
                    variant="outlined"
                    size="small"
                    value={props.identification}
                    InputProps={{
                        readOnly: true,
                    }}
                />
            </Grid>

            {/* GPIB address selection */}
            <Grid item xs={2}>
                <FormControl fullWidth size="small">
                    <InputLabel size="small">GPIB</InputLabel>
                    <Select
                        value={props.address}
                        label="GPIB"
                        size="small"
                        onChange={(e) => props.setAddress(e.target.value)}
                    >
                        {props.addressRange.map((address) =>
                            <MenuItem
                                key={address}
                                value={address}
                            >
                                {address}
                            </MenuItem>
                        )}
                    </Select>
                </FormControl>
            </Grid>

            {/* Button to connect to instrument GPIB */}
            <Grid item xs={1.5}>
                <Button
                    fullWidth
                    variant="outlined"
                    size="large"
                    sx={{width: "100%", minWidth: "0px"}}
                >
                    🡱
                </Button>
            </Grid>

            {/* Button to disconnect from instrument GPIB */}
            <Grid item xs={1.5}>
                <Button
                    fullWidth
                    variant="outlined"
                    size="large"
                    sx={{width: "100%", minWidth: "0px"}}
                >
                    ✖
                </Button>
            </Grid>

        </Grid>
    );
};
