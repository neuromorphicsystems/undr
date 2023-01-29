import * as React from "react";
import styled from "styled-components";

interface SelectProps {
    options: [string, string][];
    value: string;
    onChange: (newValue: string) => void;
}

const StyledSelect = styled.div`
    height: 30px;
    overflow: hidden;
    position: relative;
    &:after {
        content: "▼";
        line-height: 30px;
        position: absolute;
        font-size: 8px;
        right: 10px;
        top: 1px;
        z-index: 1;
        text-align: center;
        height: 100%;
        pointer-events: none;
    }
`;

const Dropdown = styled.select`
    appearance: none;
    display: inline-block;
    height: 30px;
    line-height: 32px;
    padding-left: 10px;
    padding-right: 50px;
    font-size: 12px;
    font-weight: 400;
    border-radius: 5px;
    border: none;
    margin: 0;
    outline: none;
    background-color: ${props => props.theme.background0};
    color: ${props => props.theme.content0};
    cursor: pointer;
`;

export { StyledSelect, Dropdown };

export default function Select(props: SelectProps) {
    return (
        <StyledSelect>
            <Dropdown
                value={props.value}
                onChange={event => props.onChange(event.target.value)}
            >
                {props.options.map(([value, label]) => (
                    <option value={value} key={value}>
                        {label}
                    </option>
                ))}
            </Dropdown>
        </StyledSelect>
    );
}
