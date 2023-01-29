import * as React from "react";
import styled, { css, keyframes } from "styled-components";
import * as constants from "../hooks/constants";

interface ProgressProps {
    mode: "index" | "remote" | "local" | "raw" | "complete";
    value: null | number | [number, number];
}

const StyledProgress = styled.div`
    height: ${constants.progressHeight}px;
    width: 100%;
    background-color: ${props => props.theme.background2};
    border-radius: ${constants.progressHeight / 2}px;
    overflow: hidden;
`;

interface BarInterface {
    progress: null | number;
}

interface ModeInterface {
    mode: "index" | "remote" | "local" | "complete";
}

const index = keyframes`
    0% {
        background-position: 0 0;
    }
    100% {
        background-position: ${constants.progressHeight * 2}px ${
    constants.progressHeight * 2
}px;
    }
`;

const Bar = styled.div.attrs<BarInterface & ModeInterface>(props => ({
    style: {
        width: `${
            props.mode === "local" ? (props.progress as number) * 100 : 100
        }%`,
    },
}))<BarInterface & ModeInterface>`
    height: ${constants.progressHeight}px;
    background-image: ${props =>
        props.mode === "index"
            ? `linear-gradient(
                -45deg,
                ${props.theme.remote} 25%,
                ${props.theme.remoteActive} 25%,
                ${props.theme.remoteActive} 50%,
                ${props.theme.remote} 50%,
                ${props.theme.remote} 75%,
                ${props.theme.remoteActive} 75%,
                ${props.theme.remoteActive}
            )`
            : "none"};
    animation: ${props =>
        props.mode === "index"
            ? css`
                  ${index} 1s infinite linear
              `
            : "none"};
    background-size: ${constants.progressHeight * 2}px
        ${constants.progressHeight * 2}px;
    background-color: ${props =>
        props.mode === "remote"
            ? props.theme.remote
            : props.mode === "local"
            ? props.theme.local
            : props.mode === "complete"
            ? props.theme.complete
            : "none"};
`;

const UpperBar = styled.div.attrs<BarInterface>(props => ({
    style: {
        width: `${(props.progress as number) * 100}%`,
    },
}))<BarInterface>`
    height: ${constants.progressHeight / 2}px;
    background-color: ${props => props.theme.local};
`;

const LowerBar = styled.div.attrs<BarInterface>(props => ({
    style: {
        width: `${(props.progress as number) * 100}%`,
    },
}))<BarInterface>`
    height: ${constants.progressHeight / 2}px;
    background-color: ${props => props.theme.raw};
`;

export default function Progress(props: ProgressProps) {
    return (
        <StyledProgress>
            {props.mode === "raw" ? (
                <>
                    <UpperBar
                        progress={
                            (props.value as unknown as [number, number])[0]
                        }
                    />
                    <LowerBar
                        progress={
                            (props.value as unknown as [number, number])[1]
                        }
                    />
                </>
            ) : (
                <Bar
                    mode={props.mode}
                    progress={props.value as unknown as null | number}
                />
            )}
        </StyledProgress>
    );
}
