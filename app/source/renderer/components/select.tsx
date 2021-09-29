import React, { useState, useEffect } from "react";
import styled from "styled-components";

type Props = {
    value: string;
    options: string[];
    onChange: (value: string) => void;
};

const Select = styled.div`
    height: 40px;
    margin-left: 10px;
    margin-right: 0;
    overflow: hidden;
    position: relative;
    &:after {
        color: ${props => props.theme.content0};
        content: "▼";
        line-height: 40px;
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
    width: 100%;
    line-height: 30px;
    padding-left: 10px;
    padding-right: 50px;
    font-size: 14px;
    margin: 0;
    margin-top: 5px;
    border-radius: 5px;
    border: 1px solid ${props => props.theme.backgroundSeparator};
    outline: none;
    background-color: ${props => props.theme.background0};
    color: ${props => props.theme.content0};
    cursor: pointer;
`;

export default function (props: Props) {
    const [value, setValue] = useState(props.value);
    useEffect(() => {
        if (props.value !== value) {
            setValue(props.value);
        }
    });
    return (
        <Select>
            <Dropdown
                value={value}
                onChange={event => {
                    props.onChange(event.target.value);
                }}
            >
                {props.options.map(value => (
                    <option key={value} value={value}>
                        {value}
                    </option>
                ))}
            </Dropdown>
        </Select>
    );
}
