/**
 * Render debug data result.
 */

export const ProgramIdVds = ({
    metadata,
    data,
}) => {

    return (
        <div>
            <div>

            </div>
            <Plot
                data={[
                {
                    x: [],
                    y: [],
                    type: "scatter",
                    mode: "lines+markers",
                    marker: {color: "red"},
                },
                ]}
                layout={ {width: 600, height: 400, title: "A Fancy Plot"} }
            />
        </div>
    );
}
