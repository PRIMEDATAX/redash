import React from "react";
import PropTypes from "prop-types";
import useQueryResultData from "@/lib/useQueryResultData";

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
          <span className="policy_text m-l-5">
            <strong>WARNING:  </strong>
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
