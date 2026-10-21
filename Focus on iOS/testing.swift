import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 100) {
            Text("Hello!")
                .padding()
                .background(Color.yellow, in: RoundedRectangle(cornerRadius: 8))   
                
            Text("World!")
             .padding()
             .background(Color.teal, in: RoundedRectangle(cornerRadius: 8))
             .shadow(color: Color.green, radius: 100, x: 2, y: 2)
        }

    }
}