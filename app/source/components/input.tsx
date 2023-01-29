import * as React from "react";
import styled from "styled-components";

interface InputProps {
    value: string;
    onChange: (newValue: string) => void;
    error: boolean;
    live: boolean;
    enabled: boolean;
    [rest: string]: any;
}

interface StyledInputInterface {
    readonly error: boolean;
}

const StyledInput = styled.input<StyledInputInterface>`
    height: 30px;
    line-height: 30px;
    padding-left: ${props => (props.error ? 9 : 10)}px;
    padding-right: ${props => (props.error ? 9 : 10)}px;
    width: 90px;
    font-size: 12px;
    border-radius: 5px;
    border: ${props =>
        props.error ? `1px solid ${props.theme.error}` : "none"};
    outline: none;
    background-color: ${props => props.theme.background0};
    color: ${props => props.theme.content0};
    user-select: auto;
`;

export { StyledInput };

export default function Input(props: InputProps) {
    const { value, onChange, error, live, enabled, ...rest } = props;
    const [liveValue, setLiveValue] = React.useState(value);
    const [active, setActive] = React.useState(false);
    const input = React.useRef<HTMLInputElement>(null);
    React.useEffect(() => {
        if (!active) {
            setLiveValue(props.value);
        }
    }, [props.value, active]);
    return (
        <StyledInput
            type="text"
            error={error}
            disabled={!enabled}
            value={liveValue}
            ref={input}
            onChange={event => {
                setLiveValue(event.target.value);
                if (live) {
                    onChange(event.target.value);
                }
            }}
            onFocus={() => {
                setActive(true);
            }}
            onBlur={() => {
                setActive(false);
                onChange(liveValue);
            }}
            onKeyPress={event => {
                if (event.key === "Enter" && input.current != null) {
                    input.current.blur();
                }
            }}
            {...rest}
        />
    );
}
