import {
    Button,
    FormControl,
    Grid,
    InputLabel,
    MenuItem,
    Select,
    TextField,
} from "@mui/material";

const handleBtnConnect = (axios, msg, address) => {
    axios.put("api/controller", {
        msg: msg,
        data: {
            gpib_address: address,
        },
    });
}

const handleBtnDisconnect = (axios, msg) => {
    axios.put("api/controller", {
        msg: msg,
        data: {},
    });
}

/**
 * Instrument GPIB connection bar
 */
export const InstrumentConnection = ({
    axios,          // axios instance
    label,          // label in connection text field
    identification, // identification name of instrument after connecting
    address,        // gpib address setting
    setAddress,     // setter for gpib address
    addressRange,   // range of valid gpib addresses
    connectMsg,     // msg for connecting to instrument
    disconnectMsg,  // msg for disconnecting current instrument
}) => {
    
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
                    label={label}
                    variant="outlined"
                    size="small"
                    value={identification}
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
                        value={address}
                        label="GPIB"
                        size="small"
                        onChange={(e) => setAddress(e.target.value)}
                    >
                        {addressRange.map((address) =>
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
                    onClick={() => handleBtnConnect(axios, connectMsg, address)}
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
                    onClick={() => handleBtnDisconnect(axios, disconnectMsg)}
                >
                    ✖
                </Button>
            </Grid>

        </Grid>
    );
};
