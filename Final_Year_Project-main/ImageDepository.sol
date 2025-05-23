// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ImageDepository {
    address payable public DATA_OWNER;
    address public validationContract;
    mapping(address => bool) public auth_user;  // Mapping for authorized users

    // New struct to hold all relevant image data and parameters
    struct ImageInfo {
        string originalIpfs;       // IPFS address for the original (color) image
        string logoIpfs;           // IPFS address for the logo image (16x16 binary)
        string watermarkIpfs;      // IPFS address for the zero-watermark image (16x16 binary)
        uint256 scramblingParamA;  // Scrambling parameter "a"
        uint256 scramblingParamB;  // Scrambling parameter "b"
        uint256 N;                 // Size of the effective region
        uint256 l;                 // l-level DWT (Discrete Wavelet Transform)
        uint256 n;                 // Size of subblock
        string waveletName;        // Wavelet name used for DWT
    }

    // Mapping from an identifier (e.g., a user-provided key or image identifier)
    // to its complete ImageInfo data.
    mapping(string => ImageInfo) public imageData;  

    // Events
    event UserAuthorized(address indexed user);
    event UserRemoved(address indexed user);
    event ImageDataAdded(
        string indexed imageId,
        string originalIpfs,
        string logoIpfs,
        string watermarkIpfs,
        uint256 scramblingParamA,
        uint256 scramblingParamB,
        uint256 N,
        uint256 l,
        uint256 n,
        string waveletName
    );
    event ImageDataDeleted(string indexed imageId);
    event ValidationContractSet(address validationContract);
    event Withdrawal(address indexed owner, uint256 amount);

    constructor() {
        DATA_OWNER = payable(msg.sender);
    }

    modifier onlyOwner() {
        require(msg.sender == DATA_OWNER, "Only DATA_OWNER can perform this action");
        _;
    }

    // Set the address of the ImageValidation contract
    function setValidationContract(address _validationContract) external onlyOwner {
        validationContract = _validationContract;
        emit ValidationContractSet(_validationContract);
    }

    // Authorize a user
    function authorizeUser(address user) public onlyOwner returns (bool) {
        auth_user[user] = true;
        emit UserAuthorized(user);
        return true;
    }

    // Remove an authorized user
    function removeUser(address user) public onlyOwner returns (bool) {
        delete auth_user[user];
        emit UserRemoved(user);
        return true;
    }

    // Add new image data along with all parameters
    function addImageData(
        string memory imageId, 
        string memory originalIpfs, 
        string memory logoIpfs, 
        string memory watermarkIpfs,
        uint256 scramblingParamA,
        uint256 scramblingParamB,
        uint256 N,
        uint256 l,
        uint256 n,
        string memory waveletName
    ) public onlyOwner returns (bool) {
        imageData[imageId] = ImageInfo(
            originalIpfs,
            logoIpfs,
            watermarkIpfs,
            scramblingParamA,
            scramblingParamB,
            N,
            l,
            n,
            waveletName
        );
        emit ImageDataAdded(imageId, originalIpfs, logoIpfs, watermarkIpfs, scramblingParamA, scramblingParamB, N, l, n, waveletName);
        return true;
    }

    // Delete image data
    function deleteImageData(string memory imageId) public onlyOwner returns (bool) {
        delete imageData[imageId];
        emit ImageDataDeleted(imageId);
        return true;
    }

    // Search function to allow access by DATA_OWNER, authorized users, or validationContract
    // Returns all the stored parameters.
    function search(string memory imageId) public view returns (
        string memory originalIpfs,
        string memory logoIpfs,
        string memory watermarkIpfs,
        uint256 scramblingParamA,
        uint256 scramblingParamB,
        uint256 N,
        uint256 l,
        uint256 n,
        string memory waveletName
    ) {
        require(
            msg.sender == DATA_OWNER || auth_user[msg.sender] || msg.sender == validationContract,
            "Not authorized to access this information"
        );
        ImageInfo memory info = imageData[imageId];
        return (
            info.originalIpfs,
            info.logoIpfs,
            info.watermarkIpfs,
            info.scramblingParamA,
            info.scramblingParamB,
            info.N,
            info.l,
            info.n,
            info.waveletName
        );
    }

    // Withdraw contract balance to DATA_OWNER
    function withdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No balance to withdraw");
        DATA_OWNER.transfer(balance);
        emit Withdrawal(DATA_OWNER, balance);
    }

    // Fallback function to receive Ether
    receive() external payable {}
}
