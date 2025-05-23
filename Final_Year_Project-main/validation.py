import zero_watermark_common as zwc
import cv2
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import json
import os
from web3 import Web3
from dotenv import load_dotenv

import requests

load_dotenv()

# Load environment variables for provider URL, owner address and private key
provider_url = os.environ.get("INFURA_PROJECT_URL")  # e.g., "https://rinkeby.infura.io/v3/YOUR_INFURA_PROJECT_ID"
if not provider_url:
    raise ValueError("Please set the PROVIDER_URL environment variable.")
w3 = Web3(Web3.HTTPProvider(provider_url))
if not w3.is_connected():
    raise Exception("Web3 is not connected. Check your provider URL.")

# Owner address and private key (the account that deployed the contract)
OWNER_ADDRESS = os.environ.get("ACCOUNT_ADDRESS_2")  # e.g., "0xYourOwnerAddress"
OWNER_PRIVATE_KEY = os.environ.get("PRIVATE_KEY_2")  # e.g., "your_private_key_here"
if not OWNER_ADDRESS or not OWNER_PRIVATE_KEY:
    raise ValueError("Please set the OWNER_ADDRESS and OWNER_PRIVATE_KEY environment variables.")

# Load the ABI for the deployed ImageValidation contract
with open('ImageValidation_abi.json', 'r') as abi_file:
    validation_abi = json.load(abi_file)

# Deployed ImageValidation contract address
IMAGE_VALIDATION_ADDRESS = os.environ.get("IMAGE_VALIDATION_ADDRESS")  # e.g., "0xYourContractAddress"
if not IMAGE_VALIDATION_ADDRESS:
    raise ValueError("Please set the IMAGE_VALIDATION_ADDRESS environment variable.")

# Instantiate the ImageValidation contract
image_validation = w3.eth.contract(address=IMAGE_VALIDATION_ADDRESS, abi=validation_abi)

def search_image_validation(image_id):
    """
    Calls the state-changing search function on the ImageValidation contract.
    This function initiates the search in the underlying ImageDepository
    and stores the retrieved data on the validation contract.
    """
    nonce = w3.eth.get_transaction_count(OWNER_ADDRESS)
    txn = image_validation.functions.search(image_id).build_transaction({
        'nonce': nonce,
        'from': OWNER_ADDRESS,
        'gas': 300000,
        'gasPrice': w3.to_wei('100', 'gwei')
    })
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=OWNER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

def get_result_image_validation(image_id):
    """
    Calls the getResult function (a view function) on the ImageValidation contract.
    
    Returns a tuple that includes:
      (original_ipfs, logo_ipfs, watermark_ipfs,
       scrambling_param_a, scrambling_param_b,
       N, l, n, wavelet_name)
    """
    result = image_validation.functions.getResult(image_id).call({'from': OWNER_ADDRESS})
    return result

def download_from_ipfs(ipfs_hash, output_file):
    """
    Downloads a file from IPFS using Pinata's gateway and saves it locally.

    Args:
        ipfs_hash (str): The IPFS hash (CID) of the file to download.
        output_file (str): The local filename to save the downloaded file.
    """
    # Construct the URL to download the file via Pinata's gateway.
    url = f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors.
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive chunks.
                    f.write(chunk)
        print(f"Successfully downloaded file and saved as: {output_file}")
    except requests.RequestException as e:
        print(f"Error downloading {ipfs_hash}: {e}")

def rotation_attack(image, angle):
    """
    Rotate an image by the specified angle (in degrees) while ensuring that 
    the entire rotated image is visible by expanding the canvas.

    Parameters:
        image (numpy.ndarray): Input image.
        angle (float): The rotation angle in degrees.

    Returns:
        numpy.ndarray: The rotated image with expanded canvas.
    """
    # Grab the dimensions of the image and compute the center
    (h, w) = image.shape[:2]
    (cX, cY) = (w // 2, h // 2)

    # Compute the rotation matrix for the given angle
    M = cv2.getRotationMatrix2D((cX, cY), angle, 1.0)
    
    # Calculate the sine and cosine of rotation angle
    abs_cos = abs(M[0, 0])
    abs_sin = abs(M[0, 1])

    # Compute the new bounding dimensions of the image
    nW = int((h * abs_sin) + (w * abs_cos))
    nH = int((h * abs_cos) + (w * abs_sin))

    # Adjust the rotation matrix to take into account the translation
    M[0, 2] += (nW / 2) - cX
    M[1, 2] += (nH / 2) - cY

    # Perform the actual rotation and return the image
    rotated = cv2.warpAffine(image, M, (nW, nH))
    
    
    """
    # Create a matplotlib figure
    plt.figure(figsize=(6, 6))
    
    # Display the rotated image. If the image has an alpha channel, it will be shown.
    plt.imshow(rotated)
    plt.title(f"Rotated by {angle}°")
    plt.axis("on")
    plt.show()
    """
    return rotated

def translate_lower_right(image, tx, ty):
    """
    Translates the image toward the lower-right side by tx (x-direction) and ty (y-direction)
    while expanding the canvas so that the entire translated image is visible.
    
    Parameters:
        image (numpy.ndarray): Input image.
        tx (int): Translation in the x-direction (positive value moves image to right).
        ty (int): Translation in the y-direction (positive value moves image down).
    
    Returns:
        numpy.ndarray: The translated image with expanded canvas.
    """
    # Get original dimensions
    (h, w) = image.shape[:2]
    
    # Calculate new canvas dimensions
    new_w = w + tx
    new_h = h + ty
    
    # Create the translation matrix for lower-right translation
    M = np.float32([[1, 0, tx],
                    [0, 1, ty]])
    
    # Apply the warpAffine transformation with the new dimensions (canvas size)
    translated = cv2.warpAffine(image, M, (new_w, new_h))
    # Display using matplotlib
    """
    plt.figure(figsize=(8, 8))
    plt.imshow(translated)
    plt.title(f"Lower-Right Translation: tx = {tx}, ty = {ty}")
    plt.axis('off')
    plt.show()
    """
    return translated

def scaling_attack(image, scale_factor):
    """
    Scales an image by the specified scale factor.
    
    Parameters:
        image (numpy.ndarray): Input image.
        scale_factor (float): The factor by which to scale the image. 
                              Values less than 1 shrink the image; values greater than 1 enlarge it.
                              
    Returns:
        numpy.ndarray: The scaled image.
    """
    # Get original image dimensions
    (h, w) = image.shape[:2]
    
    # Calculate new dimensions
    new_w = int(w * scale_factor)
    new_h = int(h * scale_factor)
    
    # Resize the image using cv2.resize
    scaled_image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    """
    plt.figure(figsize=(8, 6))
    plt.imshow(scaled_image)
    plt.title(f"Scaled Image (Scale Factor: {scale_factor})")
    plt.axis('on')
    plt.show()
    """
    return scaled_image

def gaussian_noise_attack(image, variance):
    """
    Adds Gaussian noise to the input image.
    
    Parameters:
        image (numpy.ndarray): The input image (typically in BGR format, as read by cv2.imread).
        variance (float): The noise variance (σ²) to be applied. The standard deviation σ is computed as √variance.
    
    Returns:
        numpy.ndarray: The noisy image with the same shape and data type as the input.
    """
    sigma = np.sqrt(variance)
    # Generate Gaussian noise with mean=0, standard deviation=sigma, same shape as image.
    noise = np.random.normal(0, sigma, image.shape).astype(np.float32)
    
    # Convert image to float32 for noise addition
    image_float = image.astype(np.float32)
    
    # Add the noise to the image
    noisy_image = image_float + noise
    
    # Clip the pixel values to ensure they remain in the valid range
    noisy_image = np.clip(noisy_image, 0, 255).astype(image.dtype)
    """
    plt.figure(figsize=(8, 6))
    plt.imshow(noisy_image)
    plt.title(f"Gaussian Noise Attack (Variance = {variance})")
    plt.axis('off')
    plt.show()
    """
    return noisy_image

def median_filter_attack(image, window_size):
    """
    Applies a median filtering attack on the input image using the given window size.
    If an even window_size is provided, it adjusts it to the next odd number.
    
    Parameters:
        image (numpy.ndarray): The input image (as read by cv2.imread, typically in BGR format).
        window_size (int): The intended window size for the median filter (e.g., 2, 4, 8, 16).
        
    Returns:
        numpy.ndarray: The median-filtered (attacked) image.
    """
    # Adjust window_size to be odd if it isn't already
    if window_size % 2 == 0:
        ksize = window_size + 1
    else:
        ksize = window_size
    
    # Apply median filter using OpenCV
    filtered_image = cv2.medianBlur(image, ksize)
    """
    plt.figure(figsize=(6, 6))
    plt.imshow(filtered_image)
    plt.title(f"Median Filter Attack (Window Size: {window_size})")
    plt.axis('on')
    plt.show()
    """
    return filtered_image
"""
# Specify an image identifier (should match the one stored in the repository via the validation contract's search call)
image_id = "first"
    
# Call search to trigger the repository lookup and store results in the ImageValidation contract
search_receipt = search_image_validation(image_id)
print("Search Transaction Receipt:", search_receipt)
    
# Retrieve the stored image data using getResult
result = get_result_image_validation(image_id)
print("Retrieved Image Data:")
print("Original IPFS Address:", result[0])
print("Logo IPFS Address:", result[1])
print("Watermark IPFS Address:", result[2])
print("Scrambling Parameter A:", result[3])
print("Scrambling Parameter B:", result[4])
print("Effective Region (N):", result[5])
print("DWT Level (l):", result[6])
print("Subblock Size (n):", result[7])
print("Wavelet Name:", result[8])

# Replace these with the actual IPFS hashes you obtained after uploading.
original_image_hash = result[0]
logo_image_hash = result[1]
zero_watermark_hash = result[2]
"""
# Define file names to save the downloaded images.
original_image_file = "downloaded_original_image.png"  # Color image
logo_image_file = "downloaded_logo_image.png"          # 16x16 binary image
zero_watermark_file = "downloaded_zero_watermark.png"    # 16x16 binary image
"""
# Download each image.
download_from_ipfs(original_image_hash, original_image_file)
download_from_ipfs(logo_image_hash, logo_image_file)
download_from_ipfs(zero_watermark_hash, zero_watermark_file)
"""
img = cv2.imread(original_image_file)
if img is None:
    raise FileNotFoundError("Image file not found.")

#rotated_img = rotation_attack(img, 80)
#translated_img = translate_lower_right(img, 50, 50)

#scaled_img = scaling_attack(img, 1.5)

#noisy_img = gaussian_noise_attack(img, 100.0)
#filtered_img = median_filter_attack(img, 15)

# Load the binary logo image "logo_H.png"
v_img = Image.open(zero_watermark_file).convert('1')
# Convert to a NumPy array and normalize values: in mode '1' pixels might be 0 or 255, so we convert them to 0 or 1
v_arr = (np.array(v_img, dtype=np.uint8) > 0).astype(np.uint8)

N = 128
l = 2
n = 2
wavelet_name = 'haar'
"""
recovered_logo = zwc.recover_logo_image(filtered_img, N, l, n, wavelet_name, v_arr)
nc = zwc.compute_normalized_correlation(logo_image_file, recovered_logo)
print("Normalized Correlation (NC) value:", nc)
"""


# --- NC vs. Rotation Angle ---
angles = [0, 3, 5, 8, 10, 12, 15, 20, 25, 30, 45]  # degrees to test
nc_rot = []

for angle in angles:
    attacked = rotation_attack(img, angle)
    rec_path = zwc.recover_logo_image(attacked, N, l, n, wavelet_name, v_arr)
    nc = zwc.compute_normalized_correlation(logo_image_file, rec_path)
    nc_rot.append(nc)
    print(f"Rotation {angle}° → NC = {nc:.4f}")

plt.figure(figsize=(8,5))
plt.plot(angles, nc_rot, marker='o', linestyle='-')
plt.title('Normalized Correlation vs. Rotation Angle')
plt.xlabel('Rotation Angle (degrees)')
plt.ylabel('NC')
plt.grid(True)

plt.xticks(angles)
plt.tight_layout()
plt.show()

# --- NC vs. Translation Magnitude (lower-right) ---
translations = [0, 5, 10, 15, 20, 25, 30, 40, 50]  # pixels
nc_trans = []

for t in translations:
    attacked = translate_lower_right(img, t, t)
    rec_path = zwc.recover_logo_image(attacked, N, l, n, wavelet_name, v_arr)
    nc = zwc.compute_normalized_correlation(logo_image_file, rec_path)
    nc_trans.append(nc)
    print(f"Translation {t}px → NC = {nc:.4f}")

plt.figure(figsize=(8,5))
plt.plot(translations, nc_trans, marker='o', linestyle='-')
plt.title('Normalized Correlation vs. Translation (px)')
plt.xlabel('Translation (pixels)')
plt.ylabel('NC')
plt.grid(True)
plt.xticks(translations)
plt.tight_layout()
plt.show()

# --- NC vs. Scaling Factor ---
scales = [0.5, 0.6, 0.75, 0.9, 1.0, 1.1, 1.25, 1.4, 1.5]
nc_scale = []

for s in scales:
    attacked = scaling_attack(img, s)
    rec_path = zwc.recover_logo_image(attacked, N, l, n, wavelet_name, v_arr)
    nc = zwc.compute_normalized_correlation(logo_image_file, rec_path)
    nc_scale.append(nc)
    print(f"Scale {s}× → NC = {nc:.4f}")

plt.figure(figsize=(8,5))
plt.plot(scales, nc_scale, marker='o', linestyle='-')
plt.title('Normalized Correlation vs. Scaling Factor')
plt.xlabel('Scale Factor')
plt.ylabel('NC')
plt.grid(True)
plt.xticks(scales)
plt.tight_layout()
plt.show()

# --- NC vs. Gaussian Noise Variance ---
variances = [1.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0]  # σ² values
nc_noise = []

for var in variances:
    attacked = gaussian_noise_attack(img, var)
    rec_path = zwc.recover_logo_image(attacked, N, l, n, wavelet_name, v_arr)
    nc = zwc.compute_normalized_correlation(logo_image_file, rec_path)
    nc_noise.append(nc)
    print(f"Variance {var} → NC = {nc:.4f}")

plt.figure(figsize=(8,5))
plt.plot(variances, nc_noise, marker='o', linestyle='-')
plt.title('Normalized Correlation vs. Gaussian Noise Variance')
plt.xlabel('Variance (σ²)')
plt.ylabel('NC')
plt.grid(True)
plt.xticks(variances)
plt.tight_layout()
plt.show()

kernel_sizes = [3, 5, 7, 9, 11, 13, 15]  # you can adjust this list as needed

nc_values = []

for k in kernel_sizes:
    # apply median filter attack
    attacked = median_filter_attack(img, k)
    
    # recover the logo from the attacked image
    recovered_logo_path = zwc.recover_logo_image(attacked, N, l, n, wavelet_name, v_arr)
    
    # compute NC against the original logo
    nc = zwc.compute_normalized_correlation(logo_image_file, recovered_logo_path)
    nc_values.append(nc)
    print(f"Window size {k}: NC = {nc:.4f}")

# plot the results
plt.figure(figsize=(8,5))
plt.plot(kernel_sizes, nc_values, marker='o', linestyle='-')
plt.title('Normalized Correlation vs. Median Filter Window Size')
plt.xlabel('Median Filter Window Size')
plt.ylabel('Normalized Correlation (NC)')
plt.grid(True)
plt.xticks(kernel_sizes)
plt.tight_layout()
plt.show()


"""

nc = zwc.compute_normalized_correlation('logo_H.png', 'recovered_scrambled_logo.png')
print("Normalized Correlation (NC) value:", nc)
"""

"""
# An authentication decision based on a predetermined threshold
authentication_threshold = 0.90  # Adjust this threshold as required
if nc > authentication_threshold:
    print("Copyright authentication is successful.")
else:
    print("Copyright authentication is failed.")
"""
