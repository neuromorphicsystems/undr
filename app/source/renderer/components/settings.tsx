import React, { useState } from "react";
import styled from "styled-components";
import Input from "./input";
import Label, { Label as StyledLabel } from "./label";
import Select from "./select";
import Switch from "./switch";

type Props = {
    themeName: string;
    onThemeNameChange: (name: string) => void;
    timeout: number;
    onTimeoutChange: (timeout: number) => void;
    workersCount: number;
    onWorkersCountChange: (workersCount: number) => void;
};

const Settings = styled.div`
    overflow: hidden;
    flex-grow: 1;
    background-color: ${props => props.theme.background1};
    display: flex;
    flex-direction: column;
`;

const Title = styled.div`
    width: 100%;
    flex-shrink: 0;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    font-size: 15px;
    align-items: center;
    padding: 15px;
    color: ${props => props.theme.content1};
    border-bottom: 1px solid ${props => props.theme.backgroundSeparator};
    background-color: ${props => props.theme.background2};
`;

const ContentWrapper = styled.div`
    flex-grow: 1;
    width: 100%;
    overflow-y: auto;
    display: flex;
    justify-content: center;
`;

const Content = styled.div`
    width: 100%;
    padding: 20px;
`;

const Row = styled.div`
    max-width: 700px;
    padding-bottom: 20px;
    margin-left: auto;
    margin-right: auto;
`;

const Control = styled.div`
    flex-shrink: 0;
    display: flex;
    & > * {
        width: 155px;
    }
    & > ${StyledLabel} {
        width: 190px;
    }
    & > ${StyledLabel}:first-of-type {
        width: 180px;
    }
`;

const Info = styled.div`
    padding-top: 3px;
    padding-left: 10px;
    margin-left: 180px;
    color: ${props => props.theme.content2};
    font-style: italic;
`;

export default function (props: Props) {
    const [timeoutError, setTimeoutError] = useState(false);
    const [workersCountError, setWorkersCountError] = useState(false);
    return (
        <Settings>
            <Title>Settings</Title>
            <ContentWrapper>
                <Content>
                    <Row>
                        <Control>
                            <Label label={"Theme"} right={true} />
                            <Select
                                value={props.themeName}
                                options={["System default", "Light", "Dark"]}
                                onChange={props.onThemeNameChange}
                            />
                            <Label label={""} right={false} />
                        </Control>
                        <Info />
                    </Row>
                    <Row>
                        <Control>
                            <Label label={"Timeout"} right={true} />
                            <Input
                                value={props.timeout.toString()}
                                live={true}
                                error={timeoutError}
                                onChange={value => {
                                    const timeout = parseFloat(value);
                                    const valid =
                                        !isNaN(timeout) && timeout > 0.0;
                                    setTimeoutError(!valid);
                                    if (valid) {
                                        props.onTimeoutChange(timeout);
                                    }
                                }}
                            />
                            <Label label={"seconds"} right={false} />
                        </Control>
                        <Info>
                            Time to wait for a server response before raising an
                            error.
                        </Info>
                    </Row>
                    <Row>
                        <Control>
                            <Label label={"Workers"} right={true} />
                            <Input
                                value={props.workersCount.toString()}
                                live={true}
                                error={workersCountError}
                                onChange={value => {
                                    const workersCount = parseInt(value.trim());
                                    const valid =
                                        /^\d+$/.test(value.trim()) &&
                                        workersCount >= 1;
                                    setWorkersCountError(!valid);
                                    if (valid) {
                                        props.onWorkersCountChange(
                                            workersCount
                                        );
                                    }
                                }}
                            />
                            <Label label={"threads"} right={false} />
                        </Control>
                        <Info>
                            Number of parallel file downloads. This number
                            should be relatively large to maximise download
                            speed. This is especially important for datasests
                            with many small files.
                        </Info>
                    </Row>
                    <Row>
                        <Control>
                            <Label label={"Always re-download"} right={true} />
                            <Switch value={true} onChange={() => {}} />
                            <Label label={""} right={false} />
                        </Control>
                        <Info>
                            Always (re-)download files from the server even if
                            they are already partially or fully downloaded.
                        </Info>
                    </Row>
                </Content>
            </ContentWrapper>
        </Settings>
    );
}
