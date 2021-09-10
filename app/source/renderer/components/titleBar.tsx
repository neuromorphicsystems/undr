import React from "react";
import styled from "styled-components";
import Gear from "../icons/gear.svg";
import TitleBarLogo from "../icons/titleBarLogo.svg";

type Props = {};

const StyledTitleBar = styled.div`
    position: relative;
    background-color: #ffaf00;
    -webkit-user-select: none;
    -webkit-app-region: drag;
    height: 52px;
    padding-left: 11px;
    padding-right: 11px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    & > svg {
        height: 40px;
    }
`;

const Placeholder = styled.div`

`;

const Button = styled.div`
    width: 30px;
    height: 30px;
    cursor: pointer;
    & path {
        transition: fill 0.2s
    }
    &:hover path {
        fill: #eeeeee;
    }
`;

const TitleBar: React.FC<Props> = props => {
    return (
        <StyledTitleBar>
            <Placeholder />
            <TitleBarLogo />
            <Button>
                <Gear />
            </Button>
        </StyledTitleBar>
    );
};

export default TitleBar;
