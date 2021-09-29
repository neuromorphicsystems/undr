import React from "react";
import styled from "styled-components";

type Props = {
    value: boolean;
    onChange: (value: boolean) => void;
};

const Switch = styled.div`
    margin-top: 10px;
    margin-bottom: 10px;
    margin-left: 15px;
    margin-right: 15px;
    height: 20px;
    width: 30px;
    border-radius: 15px;
    cursor: pointer;
    position: relative;
`;

const Track = styled.div<{ $value: boolean }>`
    position: absolute;
    top: 3px;
    width: 30px;
    height: 14px;
    border-radius: 7px;
    background-color: ${props =>
        props.$value
            ? props.theme.controlBackgroundActive
            : props.theme.controlBackground};
`;

const Shadow = styled.div<{ $value: boolean }>`
    position: absolute;
    opacity: 0;
    top: -10px;
    width: 40px;
    height: 40px;
    border-radius: 20px;
    background-color: ${props =>
        props.$value
            ? props.theme.controlForegroundActive
            : props.theme.content2};
    left: ${props => (props.$value ? "5px" : "-15px")};
    transition: opacity 0.2s, background-color 0.2s, left 0.2s;
    ${Switch}:hover &, ${Switch}:active & {
        opacity: 0.2;
    }
`;

const Thumb = styled.div<{ $value: boolean }>`
    position: absolute;
    top: 0;
    width: 20px;
    height: 20px;
    border-radius: 10px;
    box-shadow: 0 0 5px ${props => props.theme.controlShadow};
    background-color: ${props =>
        props.$value
            ? props.theme.controlForegroundActive
            : props.theme.controlForeground};
    left: ${props => (props.$value ? "15px" : "-5px")};
    transition: left 0.2s;
`;

export default function (props: Props) {
    return (
        <Switch onClick={() => props.onChange(!props.value)}>
            <Track $value={props.value} />
            <Shadow $value={props.value} />
            <Thumb $value={props.value} />
        </Switch>
    );
}
