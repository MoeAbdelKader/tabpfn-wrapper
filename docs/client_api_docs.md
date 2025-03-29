browser_auth ¶
BrowserAuthHandler ¶
try_browser_login ¶

try_browser_login() -> Tuple[bool, Optional[str]]
Attempts to perform browser-based login Returns (success: bool, token: Optional[str])


client ¶
DatasetUIDCacheManager ¶
Manages a cache of the last 50 uploaded datasets, tracking dataset hashes and their UIDs.

add_dataset_uid ¶

add_dataset_uid(hash: str, dataset_uid: str)
Adds a new dataset to the cache, removing the oldest item if the cache exceeds 50 entries. Assumes the dataset is not already in the cache.

delete_uid ¶

delete_uid(dataset_uid: str) -> Optional[str]
Deletes an entry from the cache based on the dataset UID.

get_dataset_uid ¶

get_dataset_uid(*args)
Generates hash by all received arguments and returns cached dataset uid if in cache, otherwise None.

load_cache ¶

load_cache()
Loads the cache from disk if it exists, otherwise initializes an empty cache.

save_cache ¶

save_cache()
Saves the current cache to disk.

GCPOverloaded ¶
Bases: Exception

Exception raised when the Google Cloud Platform service is overloaded or unavailable.

ServiceClient ¶
Bases: Singleton

Singleton class for handling communication with the server. It encapsulates all the API calls to the server.

delete_all_datasets classmethod ¶

delete_all_datasets() -> [str]
Delete all datasets uploaded by the user from the server.

Returns¶
deleted_dataset_uids : [str] The list of deleted dataset UIDs.

delete_dataset classmethod ¶

delete_dataset(dataset_uid: str) -> list[str]
Delete the dataset with the provided UID from the server. Note that deleting a train set with lead to deleting all associated test sets.

Parameters¶
dataset_uid : str The UID of the dataset to be deleted.

Returns¶
deleted_dataset_uids : [str] The list of deleted dataset UIDs.

download_all_data classmethod ¶

download_all_data(save_dir: Path) -> Union[Path, None]
Download all data uploaded by the user from the server.

Returns¶
save_path : Path | None The path to the downloaded file. Return None if download fails.

fit classmethod ¶

fit(X, y, config=None) -> str
Upload a train set to server and return the train set UID if successful.

Parameters¶
X : array-like of shape (n_samples, n_features) The training input samples. y : array-like of shape (n_samples,) or (n_samples, n_outputs) The target values. config : dict, optional Configuration for the fit method. Includes tabpfn_systems and paper_version.

Returns¶
train_set_uid : str The unique ID of the train set in the server.

get_api_usage classmethod ¶

get_api_usage(access_token: str)
Retrieve current API usage data of the user from the server. Returns summary: str

get_data_summary classmethod ¶

get_data_summary() -> dict
Get the data summary of the user from the server.

Returns¶
data_summary : dict The data summary returned from the server.

get_password_policy classmethod ¶

get_password_policy() -> dict
Get the password policy from the server.

Returns¶
password_policy : {} The password policy returned from the server.

is_auth_token_outdated classmethod ¶

is_auth_token_outdated(access_token) -> Union[bool, None]
Check if the provided access token is valid and return True if successful.

login classmethod ¶

login(email: str, password: str) -> tuple[str, str]
Login with the provided credentials and return the access token if successful.

Parameters¶
email : str password : str

Returns¶
access_token : str | None The access token returned from the server. Return None if login fails. message : str The message returned from the server.

predict classmethod ¶

predict(
    train_set_uid: str,
    x_test,
    task: Literal["classification", "regression"],
    predict_params: Union[dict, None] = None,
    tabpfn_config: Union[dict, None] = None,
    X_train=None,
    y_train=None,
) -> dict[str, ndarray]
Predict the class labels for the provided data (test set).

Parameters¶
train_set_uid : str The unique ID of the train set in the server. x_test : array-like of shape (n_samples, n_features) The test input.

Returns¶
y_pred : array-like of shape (n_samples,) The predicted class labels.

register classmethod ¶

register(
    email: str,
    password: str,
    password_confirm: str,
    validation_link: str,
    additional_info: dict,
)
Register a new user with the provided credentials.

Parameters¶
email : str password : str password_confirm : str validation_link: str additional_info : dict

Returns¶
is_created : bool True if the user is created successfully. message : str The message returned from the server.

retrieve_greeting_messages classmethod ¶

retrieve_greeting_messages() -> list[str]
Retrieve greeting messages that are new for the user.

send_reset_password_email classmethod ¶

send_reset_password_email(email: str) -> tuple[bool, str]
Let the server send an email for resetting the password.

send_verification_email classmethod ¶

send_verification_email(
    access_token: str,
) -> tuple[bool, str]
Let the server send an email for verifying the email.

try_browser_login classmethod ¶

try_browser_login() -> tuple[bool, str]
Attempts browser-based login flow Returns (success: bool, message: str)

try_connection classmethod ¶

try_connection() -> bool
Check if server is reachable and accepts the connection.

validate_email classmethod ¶

validate_email(email: str) -> tuple[bool, str]
Send entered email to server that checks if it is valid and not already in use.

Parameters¶
email : str

Returns¶
is_valid : bool True if the email is valid. message : str The message returned from the server.

verify_email classmethod ¶

verify_email(
    token: str, access_token: str
) -> tuple[bool, str]
Verify the email with the provided token.

Parameters¶
token : str access_token : str

Returns¶
is_verified : bool True if the email is verified successfully. message : str The message returned from the server.


estimator ¶
TabPFNClassifier ¶
Bases: ClassifierMixin, BaseEstimator, TabPFNModelSelection

predict ¶

predict(X)
Predict class labels for samples in X.

Parameters:

Name	Type	Description	Default
X		The input samples.	required
Returns:

Type	Description
The predicted class labels.
predict_proba ¶

predict_proba(X)
Predict class probabilities for X.

Parameters:

Name	Type	Description	Default
X		The input samples.	required
Returns:

Type	Description
The class probabilities of the input samples.
TabPFNModelSelection ¶
Base class for TabPFN model selection and path handling.

TabPFNRegressor ¶
Bases: RegressorMixin, BaseEstimator, TabPFNModelSelection

predict ¶

predict(
    X: ndarray,
    output_type: Literal[
        "mean",
        "median",
        "mode",
        "quantiles",
        "full",
        "main",
    ] = "mean",
    quantiles: Optional[list[float]] = None,
) -> Union[ndarray, list[ndarray], dict[str, ndarray]]
Predict regression target for X.

Parameters¶
X : array-like of shape (n_samples, n_features) The input samples. output_type : str, default="mean" The type of prediction to return: - "mean": Return mean prediction - "median": Return median prediction - "mode": Return mode prediction - "quantiles": Return predictions for specified quantiles - "full": Return full prediction details - "main": Return main prediction metrics quantiles : list[float] or None, default=None Quantiles to compute when output_type="quantiles". Default is [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

Returns¶
array-like or dict The predicted values.

validate_data_size ¶

validate_data_size(
    X: ndarray, y: Union[ndarray, None] = None
)
Check the integrity of the training data. - check if the number of rows between X and y is consistent if y is not None (ValueError) - check if the number of rows is less than MAX_ROWS (ValueError) - check if the number of columns is less than MAX_COLS (ValueError)

mock_prediction ¶
check_api_credits ¶

check_api_credits(func)
Decorator that first runs the decorated function in mock mode to simulate its credit usage. If user has enough credits, function is then executed for real.

mock_mode ¶

mock_mode()
Context manager that enables mock mode in the current thread.

mock_predict ¶

mock_predict(
    X_test,
    task: Literal["classification", "regression"],
    train_set_uid: str,
    X_train,
    y_train,
    config=None,
    predict_params=None,
)
Mock function for prediction, which can be called instead of the real prediction function. Outputs random results in the expacted format and keeps track of the simulated cost and time.


rompt_agent ¶
PromptAgent ¶
password_req_to_policy staticmethod ¶

password_req_to_policy(password_req: list[str])
Small function that receives password requirements as a list of strings like "Length(8)" and returns a corresponding PasswordPolicy object.


service_wrapper ¶
InferenceClient ¶
Bases: ServiceClientWrapper, Singleton

Wrapper of ServiceClient to handle inference, including: - fitting - prediction - mock prediction

UserAuthenticationClient ¶
Bases: ServiceClientWrapper, Singleton

Wrapper of ServiceClient to handle user authentication, including: - user registration and login - access token caching

This is implemented as a singleton class with classmethods.

try_browser_login classmethod ¶

try_browser_login() -> tuple[bool, str]
Try to authenticate using browser-based login

UserDataClient ¶
Bases: ServiceClientWrapper, Singleton

Wrapper of ServiceClient to handle user data, including: - query, or delete user account data - query, download, or delete uploaded data


expense_estimation ¶
estimate_duration ¶

estimate_duration(
    num_rows: int,
    num_features: int,
    task: Literal["classification", "regression"],
    tabpfn_config: dict = {},
    duration_factor: float = VERTEX_GPU_FACTOR,
    latency_offset: float = 0.0,
) -> float
Estimates the duration of a prediction task.


utils ¶
PreprocessorConfig dataclass ¶
Configuration for data preprocessors.

Attributes:

Name	Type	Description
name	Literal['per_feature', 'power', 'safepower', 'power_box', 'safepower_box', 'quantile_uni_coarse', 'quantile_norm_coarse', 'quantile_uni', 'quantile_norm', 'quantile_uni_fine', 'quantile_norm_fine', 'robust', 'kdi', 'none', 'kdi_random_alpha', 'kdi_uni', 'kdi_random_alpha_uni', 'adaptive', 'norm_and_kdi', 'kdi_alpha_0.3_uni', 'kdi_alpha_0.5_uni', 'kdi_alpha_0.8_uni', 'kdi_alpha_1.0_uni', 'kdi_alpha_1.2_uni', 'kdi_alpha_1.5_uni', 'kdi_alpha_2.0_uni', 'kdi_alpha_3.0_uni', 'kdi_alpha_5.0_uni', 'kdi_alpha_0.3', 'kdi_alpha_0.5', 'kdi_alpha_0.8', 'kdi_alpha_1.0', 'kdi_alpha_1.2', 'kdi_alpha_1.5', 'kdi_alpha_2.0', 'kdi_alpha_3.0', 'kdi_alpha_5.0']	Name of the preprocessor.
categorical_name	Literal['none', 'numeric', 'onehot', 'ordinal', 'ordinal_shuffled', 'ordinal_very_common_categories_shuffled']	Name of the categorical encoding method. Options: "none", "numeric", "onehot", "ordinal", "ordinal_shuffled", "none".
append_original	bool	Whether to append original features to the transformed features
subsample_features	float	Fraction of features to subsample. -1 means no subsampling.
global_transformer_name	Union[str, None]	Name of the global transformer to use.
to_dict ¶

to_dict() -> Dict[str, Any]
Convert the PreprocessorConfig instance to a dictionary.

Returns:

Type	Description
Dict[str, Any]	Dict[str, Any]: Dictionary containing the configuration parameters.