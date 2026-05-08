import pandas as pd
import great_expectations as gx
from pathlib import Path
from typing import Dict, Any, Optional


class DataValidation:
    """
    Centralized data validation using Great Expectations.
    Handles dataset validation against defined expectations for the Movies data.
    """

    def __init__(
        self,
        suite_name: str = "movies_raw_suite",
        checkpoint_name: str = "movies_raw_checkpoint",
    ):
        """
        Initialize the DataValidation handler.

        Args:
            suite_name: Name of the expectation suite
            checkpoint_name: Name of the checkpoint
        """
        self.suite_name = suite_name
        self.checkpoint_name = checkpoint_name
        self.result: Optional[Dict[str, Any]] = None
        self.context = None

    def _initialize_context(self):
        """Initialize Great Expectations context from project directory."""
        try:
            self.context = gx.get_context(mode="file", project_root_dir="/app")
            print("✓ GX context initialized from /app")
        except Exception as e:
            print(f"Warning initializing context from /app/gx: {e}")
            try:
                self.context = gx.get_context()
                print("✓ GX context initialized (ephemeral)")
            except Exception as e2:
                print(f"Error initializing ephemeral context: {e2}")
                raise

    def validate(self, df: pd.DataFrame) -> Dict[str, Any]:
        try:
            print(f"Starting GX validation with {len(df)} rows")
            self._initialize_context()

            # 1. Datasource
            datasource_name = "movies_pandas_datasource"
            try:
                datasource = self.context.data_sources.add_pandas(name=datasource_name)
            except Exception:
                datasource = self.context.data_sources.get(datasource_name)

            # 2. Asset
            asset_name = "movies_data_asset"
            try:
                asset = datasource.add_dataframe_asset(name=asset_name)
            except Exception:
                asset = datasource.get_asset(asset_name)

            batch_definition_name = "movies_batch_def"
            try:
                batch_def = asset.add_batch_definition(name=batch_definition_name)
            except Exception:
                batch_def = asset.get_batch_definition(batch_definition_name)

            try:
                expectation_suite = self.context.suites.add(
                    gx.ExpectationSuite(name=self.suite_name)
                )
            except Exception:
                expectation_suite = self.context.suites.get(self.suite_name)

            expectation_suite.expectations = []

            expectation_suite.add_expectation(
                gx.expectations.ExpectColumnToExist(column="id")
            )
            expectation_suite.add_expectation(
                gx.expectations.ExpectColumnValuesToNotBeNull(column="id")
            )
            expectation_suite.add_expectation(
                gx.expectations.ExpectColumnValuesToBeUnique(column="id")
            )

            expectation_suite.add_expectation(
                gx.expectations.ExpectColumnToExist(column="title")
            )
            expectation_suite.add_expectation(
                gx.expectations.ExpectColumnValuesToNotBeNull(column="title")
            )

            if "release_date" in df.columns:
                expectation_suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToBeBetween(
                        column="release_date",
                        min_value="1800-01-01",
                        max_value="2050-12-31",
                        mostly=0.99,
                    )
                )

            for numeric_col in ["vote_average", "popularity"]:
                if numeric_col in df.columns:
                    expectation_suite.add_expectation(
                        gx.expectations.ExpectColumnValuesToBeOfType(
                            column=numeric_col,
                            type_="float",
                        )
                    )

            if "vote_average" in df.columns:
                expectation_suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToBeBetween(
                        column="vote_average",
                        min_value=0,
                        max_value=10,
                        mostly=0.99,
                    )
                )

            if "vote_count" in df.columns:
                expectation_suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToBeBetween(
                        column="vote_count",
                        min_value=0,
                        max_value=None,
                    )
                )
            for numeric_col in ["revenue", "vote_count"]:
                if numeric_col in df.columns:
                    expectation_suite.add_expectation(
                            gx.expectations.ExpectColumnValuesToBeOfType(
                                column=numeric_col,
                                type_="int",
                            )
                        )

            if "budget" in df.columns:
                expectation_suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToBeBetween(
                        column="budget",
                        min_value=0,
                        max_value=None,
                    )
                )

            if "original_language" in df.columns:
                expectation_suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToNotBeNull(
                        column="original_language"
                    )
                )
                expectation_suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToMatchRegex(
                        column="original_language",
                        regex=r"^[a-z]{2}$",
                        mostly=0.98,
                    )
                )

            if "status" in df.columns:
                expectation_suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToBeInSet(
                        column="status",
                        value_set=[
                            "Rumored",
                            "Planned",
                            "In Production",
                            "Post Production",
                            "Released",
                            "Canceled",
                        ],
                        mostly=0.9,  
                    )
                )

            for col in ["genres", "production_companies", "production_countries"]:
                if col in df.columns:
                    expectation_suite.add_expectation(
                        gx.expectations.ExpectColumnValuesToBeOfType(
                            column=col,
                            type_="str",
                        )
                    )

            validation_def = gx.ValidationDefinition(
                data=batch_def,
                suite=expectation_suite,
                name="movies_validations",
            )
            validation_def = self.context.validation_definitions.add_or_update(
                validation_def
            )
            print("✓ Validation definition ready")

            # 6. Checkpoint
            checkpoint = gx.Checkpoint(
                name=self.checkpoint_name,
                validation_definitions=[validation_def],
                result_format={"result_format": "COMPLETE"},
            )
            checkpoint = self.context.checkpoints.add_or_update(checkpoint)
            print("✓ Checkpoint ready")

            results = checkpoint.run(batch_parameters={"dataframe": df})

            try:
                self.context.build_data_docs()
                print("✓ Data Docs built at /app/gx/uncommitted/data_docs/local_site/")
            except Exception as e:
                print(f"Warning: Could not build Data Docs: {e}")

            out = {
                "success": results.success,
                "message": "Validation completed successfully",
                "results": results.to_json_dict()
                if hasattr(results, "to_json_dict")
                else str(results),
            }
            self.result = out
            return out

        except Exception as e:
            print(f"Error during validation: {str(e)}")
            out = {"success": False, "error": str(e), "message": "Validation failed"}
            self.result = out
            return out

    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get the validation result."""
        return self.result
