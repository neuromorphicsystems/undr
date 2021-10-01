import React, { useState } from "react";
import styled from "styled-components";

type Props = {
    value: string;
    onChange: (value: string) => void;
    error: boolean;
    live: boolean;
};

const Input = styled.input<{ $error: boolean }>`
    height: 30px;
    margin-left: 10px;
    margin-right: 0;
    line-height: 30px;
    padding-left: 10px;
    padding-right: 10px;
    font-size: 14px;
    margin-top: 5px;
    border-radius: 5px;
    border: ${props =>
        props.$error
            ? `1px solid ${props.theme.error}`
            : `1px solid ${props.theme.backgroundSeparator}`};
    outline: none;
    background-color: ${props => props.theme.background0};
    color: ${props => props.theme.content0};
    user-select: auto;
`;

export { Input };

export default function (props: Props) {
    const [value, setValue] = useState(props.value);
    return (
        <Input
            type="text"
            $error={props.error}
            value={value}
            onChange={event => {
                setValue(event.target.value);
                if (props.live) {
                    props.onChange(event.target.value);
                }
            }}
            onBlur={() => {
                props.onChange(value);
            }}
            onKeyPress={event => {
                if (event.key === "Enter") {
                    event.currentTarget.blur();
                }
            }}
        />
    );
}
