import React from "react";
import styled from "styled-components";
import type { Dataset } from "../../common/types";
import Label from "./label";
import Select from "./select";

type Props = {
    dataset: Dataset;
};

const DatasetComponent = styled.div`
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 50px;
    padding-right: 10px;
    &:nth-child(odd) {
        background-color: ${props => props.theme.background0};
    }
    &:nth-child(even) {
        background-color: ${props => props.theme.background1};
    }
`;

export default function (props: Props) {
    return (
        <DatasetComponent>
            <Label label={props.dataset.name} right={false} />
            <Select
                value={`${props.dataset.mode
                    .charAt(0)
                    .toUpperCase()}${props.dataset.mode.slice(1)}`}
                options={["Remote", "Local", "Decompressed", "Disabled"]}
                onChange={value =>
                    window.undr.datasets.addOrUpdate({
                        ...props.dataset,
                        mode: value.toLowerCase() as Dataset["mode"],
                    })
                }
            />
        </DatasetComponent>
    );
}
