import * as React from "react";
import styled from "styled-components";
import Input, { StyledInput } from "./input";
import Switch from "./switch";

type Constraint = "none" | "positive" | "positive-strict" | "two-or-more";

interface NumberInputWithDefaultProps {
    defaultEnabled: boolean;
    defaultValue: number;
    value: number;
    integer: boolean;
    constraint: Constraint;
    unit: string | null;
    onChange: (newDefaultEnabled: boolean, newValue: number) => void;
    onErrorChange: (error: boolean) => void;
}

interface StyledNumberInputWithDefaultInterface {
    readonly unit: string | null;
}

const StyledNumberInputWithDefault = styled.div<StyledNumberInputWithDefaultInterface>`
    & ${StyledInput} {
        width: ${props => (props.unit == null ? 100 : 80)}px;
    }
`;

const Line = styled.div`
    display: flex;
    align-items: center;
    gap: 5px;
    padding-bottom: 5px;
`;

const Label = styled.div`
    color: ${props => props.theme.content1};
    padding-left: 5px;
`;

const Unit = styled.div`
    color: ${props => props.theme.content1};
    width: 20px;
    padding-left: 10px;
    overflow: hidden;
`;

const Value = styled.div`
    display: flex;
    align-items: center;
`;

function isValid(parsedValue: number, constraint: Constraint) {
    if (isNaN(parsedValue)) {
        return false;
    }
    switch (constraint) {
        case "none":
            return true;
        case "positive":
            return parsedValue >= 0;
        case "positive-strict":
            return parsedValue > 0;
        case "two-or-more":
            return parsedValue >= 2;
    }
    return false;
}

export default function NumberInputWithDefault(
    props: NumberInputWithDefaultProps
) {
    const [value, setValue] = React.useState(props.value.toString());
    const [error, setError] = React.useState(false);
    return (
        <StyledNumberInputWithDefault unit={props.unit}>
            <Line>
                <Label>Auto</Label>
                <Switch
                    value={props.defaultEnabled}
                    onChange={newDefaultEnabled => {
                        const parsedValue = (
                            props.integer ? parseInt : parseFloat
                        )(value);
                        if (isValid(parsedValue, props.constraint)) {
                            setError(false);
                            props.onErrorChange(false);
                            props.onChange(newDefaultEnabled, parsedValue);
                        } else {
                            setError(!newDefaultEnabled);
                            props.onErrorChange(!newDefaultEnabled);
                            props.onChange(newDefaultEnabled, props.value);
                        }
                    }}
                />
            </Line>
            <Value>
                <Input
                    value={
                        props.defaultEnabled
                            ? props.defaultValue.toString()
                            : value
                    }
                    enabled={!props.defaultEnabled}
                    onChange={newValue => {
                        setValue(newValue);
                        const parsedValue = (
                            props.integer ? parseInt : parseFloat
                        )(newValue);
                        if (isValid(parsedValue, props.constraint)) {
                            setError(false);
                            props.onErrorChange(false);
                            props.onChange(props.defaultEnabled, parsedValue);
                        } else {
                            setError(true);
                            props.onErrorChange(true);
                        }
                    }}
                    error={error}
                    live={true}
                />
                {props.unit != null && <Unit>{props.unit}</Unit>}
            </Value>
        </StyledNumberInputWithDefault>
    );
}
