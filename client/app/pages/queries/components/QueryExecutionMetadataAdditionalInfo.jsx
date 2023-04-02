import React from "react";
import PropTypes from "prop-types";
import WarningTwoTone from "@ant-design/icons/WarningTwoTone";
import TimeAgo from "@/components/TimeAgo";
import Tooltip from "@/components/Tooltip";
import useAddToDashboardDialog from "../hooks/useAddToDashboardDialog";
import useEmbedDialog from "../hooks/useEmbedDialog";
import QueryControlDropdown from "@/components/EditVisualizationButton/QueryControlDropdown";
import EditVisualizationButton from "@/components/EditVisualizationButton";
import useQueryResultData from "@/lib/useQueryResultData";
import {durationHumanize, formatNumber, pluralize, prettySize} from "@/lib/utils";

import "./QueryExecutionMetadataAdditionalInfo.less";

export default function QueryExecutionMetadataAdditionalInfo({
                                                 query,
                                                 queryResult,
                                                 isQueryExecuting,
                                                 selectedVisualization,
                                                 showEditVisualizationButton,
                                                 onEditVisualization,
                                                 extraActions,
                                               }) {
  const queryResultData = useQueryResultData(queryResult);
  return (
    <div className="query-execution-metadata">
      {extraActions}
      <span className="m-l-5 m-r-10">
        {queryResultData.metadata.policy_tag_columns && (
          <span className="m-l-5" >
            <strong>Policy tagged columns used:  </strong>
            {queryResultData.metadata.policy_tag_columns}
          </span>
        )}
      </span>
    </div>
  );
}

QueryExecutionMetadataAdditionalInfo.propTypes = {
  query: PropTypes.object.isRequired, // eslint-disable-line react/forbid-prop-types
  queryResult: PropTypes.object.isRequired, // eslint-disable-line react/forbid-prop-types
  isQueryExecuting: PropTypes.bool,
  selectedVisualization: PropTypes.number,
  showEditVisualizationButton: PropTypes.bool,
  onEditVisualization: PropTypes.func,
  extraActions: PropTypes.node,
};

QueryExecutionMetadataAdditionalInfo.defaultProps = {
  isQueryExecuting: false,
  selectedVisualization: null,
  showEditVisualizationButton: false,
  onEditVisualization: () => {
  },
  extraActions: null,
};
