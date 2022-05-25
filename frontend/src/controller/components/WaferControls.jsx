import {
    Box,
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
 * Wafer controller
 */
export const WaferControls = ({
    axios,
}) => {
    return (
        <Box id="wafer-controls" sx={{width: "100%"}}>
            <Grid
                container
                spacing={1}
                direction="row"
            >
                {/* Wafer controls */}
                <Grid item xs={6}  align="center" sx={{width: "100%", height: "100%"}}>
                    <Box sx={{width: "100%"}}>
                        <Grid
                            container
                            direction="row"
                            spacing={1}
                            columns={12}
                        >
                            <Grid item xs={6}>
                                <Box sx={{
                                    width: "160px",
                                    height: "160px",
                                    backgroundColor: "rgba(0,0,0,0.05)",
                                    border: "1px solid grey",
                                    borderRadius: "50%",
                                }}/>
                            </Grid>

                            <Grid item xs={6}>
                                <Grid
                                    container
                                    direction="row"
                                    spacing={1}
                                    columns={12}
                                >
                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Die Size X"
                                            variant="outlined"
                                            size="small"
                                            defaultValue="0"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Die Size Y"
                                            variant="outlined"
                                            size="small"
                                            defaultValue="0"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Offset X"
                                            variant="outlined"
                                            size="small"
                                            defaultValue="0"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Offset Y"
                                            variant="outlined"
                                            size="small"
                                            defaultValue="0"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Current Die X"
                                            variant="outlined"
                                            size="small"
                                            defaultValue="0"
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Current Die Y"
                                            variant="outlined"
                                            size="small"
                                            defaultValue="0"
                                        />
                                    </Grid>

                                </Grid>
                            </Grid>
                        </Grid>
                        
                    </Box>
                    
                </Grid>

                {/* Die controls */}
                <Grid item xs={6} align="center" sx={{width: "100%"}}>
                    <Box sx={{width: "80%"}}>
                        <Grid
                            container
                            spacing={1}
                            columns={18}
                        >
                            {/* top row: dieY control */}
                            <Grid item xs={3}/>
                            <Grid item xs={6} align="center">
                                <TextField
                                    fullWidth
                                    label="Device Y"
                                    variant="outlined"
                                    size="small"
                                    defaultValue="0"
                                />
                            </Grid>
                            <Grid item xs={9}/>
                            
                            {/* top row */}
                            <Grid item xs={4}/>
                            <Grid item xs={4}>
                                <Button variant="outlined" color="primary">
                                    🡹
                                </Button>
                            </Grid>
                            <Grid item xs={10}/>

                            {/* middle row */}
                            <Grid item xs={4}>
                                <Button variant="outlined" color="primary">
                                    🡸
                                </Button>
                            </Grid>

                            <Grid item xs={4}/>

                            <Grid item xs={4}>
                                <Button variant="outlined" color="primary">
                                    🡺
                                </Button>
                            </Grid>

                            <Grid item xs={6}>
                                <TextField
                                    fullWidth
                                    label="Device X"
                                    variant="outlined"
                                    size="small"
                                    defaultValue="0"
                                />
                            </Grid>

                            {/* bottom row */}
                            <Grid item xs={4}/>
                            <Grid item xs={4}>
                                <Button variant="outlined" color="primary">
                                    🡻
                                </Button>
                            </Grid>
                            <Grid item xs={10}/>
                        </Grid>
                    </Box>
                </Grid>

            </Grid>
            
        </Box>
    );
}
