import zero_watermark_common as zwc
import cv2
from PIL import Image
import numpy as np
import os
from dotenv import load_dotenv
import requests
import json
from web3 import Web3

load_dotenv()  # Loads variables from the .env file into os.environ

PINATA_API_KEY = os.environ.get("PINATA_API_KEY")
PINATA_SECRET_API_KEY = os.environ.get("PINATA_SECRET_API_KEY")
provider_url = os.environ.get("INFURA_PROJECT_URL")
w3 = Web3(Web3.HTTPProvider(provider_url))
if not w3.is_connected():
    raise Exception("Web3 is not connected. Check your provider URL.")

OWNER_ADDRESS = os.environ.get("ACCOUNT_ADDRESS_1")  # "0xYourOwnerAddress"
OWNER_PRIVATE_KEY = os.environ.get("PRIVATE_KEY_1")

# Load the ABI for your deployed ImageDepository contract from a JSON file
with open('ImageDepository_abi.json', 'r') as abi_file:
    image_depository_abi = json.load(abi_file)

# Deployed contract address
IMAGE_DEPOSITORY_ADDRESS = os.environ.get("IMAGE_DEPOSITORY_ADDRESS")  # "0xYourContractAddress"

# Instantiate the contract
image_depository = w3.eth.contract(address=IMAGE_DEPOSITORY_ADDRESS, abi=image_depository_abi)

if not PINATA_API_KEY or not PINATA_SECRET_API_KEY:
    raise ValueError("Please set the PINATA_API_KEY and PINATA_SECRET_API_KEY in your .env file")

# URL endpoint for Pinata file upload
PINATA_ENDPOINT = "https://api.pinata.cloud/pinning/pinFileToIPFS"

def upload_file_to_ipfs(file_path):
    """
    Uploads a file to IPFS using Pinata and returns the IPFS hash.
    """
    try:
        with open(file_path, "rb") as fp:
            # Use files parameter to send a multipart/form-data request
            files = {"file": fp}
            headers = {
                "pinata_api_key": PINATA_API_KEY,
                "pinata_secret_api_key": PINATA_SECRET_API_KEY,
            }
            response = requests.post(PINATA_ENDPOINT, files=files, headers=headers)
            response.raise_for_status()
            # The returned JSON should include an 'IpfsHash'
            json_response = response.json()
            return json_response.get("IpfsHash")
    except Exception as e:
        print(f"Error uploading {file_path}: {e}")
        return None
    
def authorize_user(user_address):
    """Calls the authorizeUser function on the ImageDepository contract."""
    nonce = w3.eth.get_transaction_count(OWNER_ADDRESS)
    txn = image_depository.functions.authorizeUser(user_address).build_transaction({
        'nonce': nonce,
        'from': OWNER_ADDRESS,
        'gas': 200000,
        'gasPrice': w3.to_wei('100', 'gwei')
    })
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=OWNER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def remove_user(user_address):
    """Calls the removeUser function on the ImageDepository contract."""
    nonce = w3.eth.get_transaction_count(OWNER_ADDRESS)
    txn = image_depository.functions.removeUser(user_address).build_transaction({
        'nonce': nonce,
        'from': OWNER_ADDRESS,
        'gas': 200000,
        'gasPrice': w3.to_wei('100', 'gwei')
    })
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=OWNER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def add_image_data(image_id, original_ipfs, logo_ipfs, watermark_ipfs,
                   scrambling_param_a, scrambling_param_b,
                   N, l, n, wavelet_name):
    """
    Calls the addImageData function on the ImageDepository contract.
    
    Parameters:
      image_id: Identifier for the image data entry (string)
      original_ipfs: IPFS hash (string) for the original image
      logo_ipfs: IPFS hash (string) for the logo image
      watermark_ipfs: IPFS hash (string) for the zero-watermark image
      scrambling_param_a: Numeric scrambling parameter a (uint256)
      scrambling_param_b: Numeric scrambling parameter b (uint256)
      N: Size of the effective region (uint256)
      l: l-level DWT (uint256)
      n: Size of subblock (uint256)
      wavelet_name: Name of the wavelet used (string)
    """
    nonce = w3.eth.get_transaction_count(OWNER_ADDRESS)
    txn = image_depository.functions.addImageData(
        image_id,
        original_ipfs,
        logo_ipfs,
        watermark_ipfs,
        scrambling_param_a,
        scrambling_param_b,
        N,
        l,
        n,
        wavelet_name
    ).build_transaction({
        'nonce': nonce,
        'from': OWNER_ADDRESS,
        'gas': 300000,
        'gasPrice': w3.to_wei('100', 'gwei')
    })
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=OWNER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def remove_image_data(image_id):
    """Calls the deleteImageData function on the ImageDepository contract to delete an image's data."""
    nonce = w3.eth.get_transaction_count(OWNER_ADDRESS)
    txn = image_depository.functions.deleteImageData(image_id).build_transaction({
        'nonce': nonce,
        'from': OWNER_ADDRESS,
        'gas': 200000,
        'gasPrice': w3.to_wei('100', 'gwei')
    })
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=OWNER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def search_image_data(image_id):
    """
    Calls the search function (a view function) on the ImageDepository contract.
    Returns a tuple:
      (original_ipfs, logo_ipfs, watermark_ipfs, scrambling_param_a,
       scrambling_param_b, N, l, n, wavelet_name)
    """
    data = image_depository.functions.search(image_id).call({'from': OWNER_ADDRESS})
    return data


img = cv2.imread('barbara.jpg')
if img is None:
    raise FileNotFoundError("Image file not found.")

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Load the binary logo image "logo_H.png"
logo_img = Image.open('logo_H.png').convert('1')
# Convert to a NumPy array and normalize values: in mode '1' pixels might be 0 or 255, so we convert them to 0 or 1
logo_arr = (np.array(logo_img, dtype=np.uint8) > 0).astype(np.uint8)

final_normalized_img = zwc.image_normalization(gray)
N = 128
effective_region, coords = zwc.effective_region_extraction(final_normalized_img, N)
zwc.visualize_effective_region(final_normalized_img, coords, effective_region)
l = 2
n = 2
wavelet_name = 'haar'
low_freq_subband = zwc.perform_wavelet_transform(effective_region, wavelet_name=wavelet_name, level=l)
print("Low-frequency subband shape:", low_freq_subband.shape)
subblocks = zwc.divide_into_subblocks(low_freq_subband, block_size=n)
print("Subblocks shape:", subblocks.shape)

# For clarity, compute K and k as defined:
k = N // (2**l * n)  # k = N / ((2^l) * n)
K = (N**2) // ((2**l * n)**2)
print("Computed k =", k)   # Expected: 16
print("Total number of subblocks K =", K)  # Expected: 256

# Compute the singular value matrix B
B = zwc.compute_singular_value_matrix(subblocks)

# Display the shape and contents of B
print("Matrix B shape:", B.shape)  # Expected (16, 16)
print("Matrix B:\n", B)

F = zwc.generate_feature_image_by_msb(B)
print("Generated Feature Image F:\n", F)
"""
# Generate dynamic key
a, b = zwc.generate_henon_key()
print(f"Generated key (a, b): {a}, {b}")

scrambled_feature = zwc.henon_scramble(F, a, b)
scrambled_watermark = zwc.henon_scramble(logo_arr, a, b)
"""
v_img = zwc.perform_XOR_operation(F, logo_arr)
# Save and/or display the resulting zero-watermark image
v_img.save('zero_watermark.png')
v_img.show()

# Define the file paths for the three images.
original_image_path = "barbara.jpg"
logo_image_path = "logo_H.png"
zero_watermark_path = "zero_watermark.png"

# Upload the Original Image
original_ipfs_hash = upload_file_to_ipfs(original_image_path)
if original_ipfs_hash:
    print(f"Original image uploaded successfully. IPFS Hash: {original_ipfs_hash}")

# Upload the Logo Image
logo_ipfs_hash = upload_file_to_ipfs(logo_image_path)
if logo_ipfs_hash:
    print(f"Logo image uploaded successfully. IPFS Hash: {logo_ipfs_hash}")

# Upload the Zero-Watermark Image
zero_watermark_ipfs_hash = upload_file_to_ipfs(zero_watermark_path)
if zero_watermark_ipfs_hash:
    print(f"Zero-watermark image uploaded successfully. IPFS Hash: {zero_watermark_ipfs_hash}")


user_address = os.environ.get("ACCOUNT_ADDRESS_2")
#receipt = authorize_user(user_address)
#print("Authorize User Receipt:", receipt)

image_id = "first"
original_ipfs = original_ipfs_hash
logo_ipfs = logo_ipfs_hash
watermark_ipfs = zero_watermark_ipfs_hash
scrambling_param_a = 123456 # Example numeric value
scrambling_param_b = 235472  # Example numeric value
receipt = add_image_data(image_id, original_ipfs, logo_ipfs, watermark_ipfs,
                             scrambling_param_a, scrambling_param_b,
                             N, l, n, wavelet_name)
print("Add Image Data Receipt:", receipt)

# Example: Search for image data
result = search_image_data(image_id)
print("Search Image Data Result:")
print("Original IPFS:", result[0])
print("Logo IPFS:", result[1])
print("Watermark IPFS:", result[2])
print("Scrambling Param A:", result[3])
print("Scrambling Param B:", result[4])
print("Effective Region N:", result[5])
print("DWT Level l:", result[6])
print("Subblock Size n:", result[7])
print("Wavelet Name:", result[8])
