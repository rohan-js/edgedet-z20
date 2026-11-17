"""
train_kaggle.py
Kaggle-friendly version of training script

Instructions:
  1. Upload this file to a Kaggle notebook
  2. Enable GPU accelerator (Settings → Accelerator → GPU)
  3. Run all cells
  4. Download the generated .inc files from /kaggle/working/weights/
  5. Copy .inc files to your local project: sw/weights/

Output: 6 weight files (.inc) + weights.npz
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
import numpy as np
import os

# ============================================================
# CNN Model (must match HLS architecture exactly)
# ============================================================
class SimpleCNN(nn.Module):
    def __init__(self, num_classes=10):
        super(SimpleCNN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=0, bias=True)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=0, bias=True)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool2d(2, 2)
        self.fc = nn.Linear(32 * 6 * 6, num_classes, bias=True)

    def forward(self, x):
        x = self.pool1(self.relu1(self.conv1(x)))
        x = self.pool2(self.relu2(self.conv2(x)))
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x


# ============================================================
# Export Weights as .inc files for ARM C code
# ============================================================
def export_weights(model, output_dir="./weights"):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[INFO] Exporting weights to {output_dir}/")

    weights = {
        'conv1_weights': model.conv1.weight.data.cpu().numpy().flatten(),
        'conv1_bias':    model.conv1.bias.data.cpu().numpy().flatten(),
        'conv2_weights': model.conv2.weight.data.cpu().numpy().flatten(),
        'conv2_bias':    model.conv2.bias.data.cpu().numpy().flatten(),
        'fc_weights':    model.fc.weight.data.cpu().numpy().flatten(),
        'fc_bias':       model.fc.bias.data.cpu().numpy().flatten(),
    }

    for name, data in weights.items():
        filepath = os.path.join(output_dir, f"{name}.inc")
        with open(filepath, 'w') as f:
            values = ", ".join([f"{v:.8f}" for v in data])
            f.write(values + "\n")
        print(f"  {name}.inc: {len(data)} values "
              f"(range: [{data.min():.4f}, {data.max():.4f}])")

    np.savez(os.path.join(output_dir, 'weights.npz'), **weights)
    print(f"  weights.npz: saved for Python testing")

    # Print total parameter count
    total = sum(len(d) for d in weights.values())
    print(f"\n  Total parameters: {total:,}")


# ============================================================
# Main Training
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  CNN Training for ZedBoard FPGA Accelerator")
    print("  (Kaggle Version)")
    print("=" * 50)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n[INFO] Using device: {device}")

    # Data transforms
    transform_train = transforms.Compose([
        transforms.RandomHorizontalFlip(),
        transforms.RandomCrop(32, padding=4),
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465),
                           (0.2470, 0.2435, 0.2616))
    ])

    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465),
                           (0.2470, 0.2435, 0.2616))
    ])

    # CIFAR-10 dataset
    print("[INFO] Loading CIFAR-10...")
    trainset = torchvision.datasets.CIFAR10(
        root='./data', train=True, download=True, transform=transform_train)
    trainloader = torch.utils.data.DataLoader(
        trainset, batch_size=64, shuffle=True, num_workers=2)

    testset = torchvision.datasets.CIFAR10(
        root='./data', train=False, download=True, transform=transform_test)
    testloader = torch.utils.data.DataLoader(
        testset, batch_size=64, shuffle=False, num_workers=2)

    # Model
    model = SimpleCNN(num_classes=10).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"[INFO] Model parameters: {param_count:,}")

    # Train
    EPOCHS = 20
    best_acc = 0
    print(f"[INFO] Training for {EPOCHS} epochs...\n")

    for epoch in range(EPOCHS):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for inputs, labels in trainloader:
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

        train_acc = 100. * correct / total
        scheduler.step()

        # Evaluate
        model.eval()
        test_correct = 0
        test_total = 0
        with torch.no_grad():
            for inputs, labels in testloader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                _, predicted = outputs.max(1)
                test_total += labels.size(0)
                test_correct += predicted.eq(labels).sum().item()

        test_acc = 100. * test_correct / test_total
        print(f"  Epoch [{epoch+1:2d}/{EPOCHS}]  "
              f"Loss: {running_loss/len(trainloader):.4f}  "
              f"Train: {train_acc:.1f}%  Test: {test_acc:.1f}%")

        if test_acc > best_acc:
            best_acc = test_acc
            torch.save(model.state_dict(), 'best_model.pth')

    print(f"\n[RESULT] Best test accuracy: {best_acc:.1f}%")

    # Load best and export
    model.load_state_dict(torch.load('best_model.pth'))
    export_weights(model, output_dir="./weights")

    print("\n" + "=" * 50)
    print("  DONE! Download the 'weights' folder.")
    print("  Copy all .inc files to your project: sw/weights/")
    print("=" * 50)
