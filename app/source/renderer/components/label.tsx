import React from "react";
import styled from "styled-components";

type Props = {
    label: string;
    right: boolean;
};

const Label = styled.div<{ $right: boolean }>`
    height: 40px;
    text-align: ${props => (props.$right ? "right" : "left")};
    line-height: 40px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    color: ${props => props.theme.content1};
    padding-right: 10px;
    padding-left: 10px;
`;

export { Label };

export default function (props: Props) {
    return <Label $right={props.right}>{props.label}</Label>;
}
