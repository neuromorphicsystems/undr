import React from "react";
import styled from "styled-components";
import Directory from "../icons/directory.svg";
import Download from "../icons/download.svg";
import List from "../icons/list.svg";

const Welcome = styled.div`
    overflow: hidden;
    flex-grow: 1;
    background-color: ${props => props.theme.background1};
    display: flex;
    flex-direction: column;
    align-items: stretch;
    justify-content: center;
`;

const Content = styled.div`
    padding: 5vw;
    overflow-y: auto;
`;

const Steps = styled.div`
    display: flex;
    gap: 5vw;
`;

const Step = styled.div`
    background-color: ${props => props.theme.background2};
    flex-grow: 1;
    border-radius: 50%;
    position: relative;
    &:before {
        content: "";
        display: block;
        margin-top: 100%;
    }
`;

const Icon = styled.div`
    position: absolute;
    display: flex;
    justify-content: center;
    bottom: 30%;
    width: 100%;
    & svg {
        width: 13vw;
        height: 13vw;
    }
    & path {
        fill: ${props => props.theme.content2};
    }
`;

const Text = styled.div`
    color: ${props => props.theme.content1};
    position: absolute;
    bottom: 10%;
    width: 100%;
    text-align: center;
    font-weight: bold;
    font-size: 2vw;
`;

const LinkContainer = styled.div`
    padding-top: 5vw;
    display: flex;
    align-items: center;
    justify-content: center;
`;

const Link = styled.div`
    background-color: ${props => props.theme.link};
    color: ${props => props.theme.titleBarContent};
    padding-top: 1.5vw;
    padding-bottom: 1.5vw;
    padding-left: 6vw;
    padding-right: 6vw;
    font-size: 3vw;
    border-radius: 1vw;
    transition: background-color 0.2s;
    cursor: pointer;
    &:hover {
        background-color: ${props => props.theme.active};
    }
    user-select: none;
`;

export default function () {
    return (
        <Welcome>
            <Content>
                <Steps>
                    <Step>
                        <Icon>
                            <Directory />
                        </Icon>
                        <Text>
                            1. Open a<br />
                            directory
                        </Text>
                    </Step>
                    <Step>
                        <Icon>
                            <List />
                        </Icon>
                        <Text>
                            2. Select
                            <br />
                            datasets
                        </Text>
                    </Step>
                    <Step>
                        <Icon>
                            <Download />
                        </Icon>
                        <Text>
                            3. Download
                            <br />
                            files
                        </Text>
                    </Step>
                </Steps>
                <LinkContainer>
                    <Link onClick={window.undr.directory.choose}>Open a directory...</Link>
                </LinkContainer>
            </Content>
        </Welcome>
    );
}
